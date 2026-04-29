"""Interactive mode: helpers, entry collection, and session loop."""
import os
import sys
from datetime import date
from typing import Callable, Dict, List, Optional, Tuple

from openproject.theme import (
    _t, _c,
    GREEN, YELLOW, RED, CYAN, BOLD, DIM,
    log_ok, log_skip, log_error, log_info, log_rule, log_section, log_divider,
)
from openproject.prompts import (
    prompt, prompt_secret, prompt_bool, prompt_choice, prompt_date, prompt_float,
    prompt_int,
    _is_exit,
)
from openproject.dates import date_range, hours_to_iso8601
from openproject.special_days import SpecialDayEntry, expand_entries, ensure_csv_from_ics, _manage_special_days
from openproject.special_days.io import load_special_day_entries
from openproject.client import OpenProjectClient
from openproject.runner import run, print_summary


def _pick_from_api_list(
    label: str,
    items: List[dict],
    name_key: str,
    id_extractor: Callable[[dict], int],
    fallback_prompt: str,
    fallback_default: Optional[int] = None,
) -> Tuple[int, str]:
    """
    Show a numbered list of API items for the user to pick from.
    Falls back to a manual ID prompt if the list is empty or fetching failed.
    Returns (id, name).
    """
    if not items:
        _no_items = _t(
            f"No {label} found via API — enter the ID manually, monke.",
            f"No {label} found via API — enter the ID manually.",
        )
        log_skip(_no_items)
        item_id = prompt_int(fallback_prompt, default=fallback_default)
        return item_id, str(item_id)

    if len(items) == 1:
        chosen    = items[0]
        item_id   = id_extractor(chosen)
        item_name = chosen.get(name_key, str(item_id))
        _one_label = _t(
            f"🐵  Only one {label} available — auto-selected:",
            f"Only one {label} available — auto-selected:",
        )
        log_info(f"{_one_label} {_c(BOLD, item_name)}  {_c(DIM, f'(ID: {item_id})')}")
        return item_id, item_name

    labels = [
        f"{item.get(name_key, '?')}  {_c(DIM, f'(ID: {id_extractor(item)})')}"
        for item in items
    ]
    idx    = prompt_choice(_t(f"🐵 Pick a {label}:", f"Select a {label}:"), labels, default=1)
    chosen = items[idx - 1]
    return id_extractor(chosen), chosen.get(name_key, str(id_extractor(chosen)))


def _href_id(href: Optional[str]) -> Optional[int]:
    """Extract the trailing integer ID from a HAL href like '/api/v3/projects/42'."""
    if not href:
        return None
    try:
        return int(href.rstrip("/").split("/")[-1])
    except (ValueError, IndexError):
        return None


def _connect_and_identify(
    base_url: str, api_key: str, insecure: bool = False
) -> Tuple[OpenProjectClient, int, str]:
    """
    Create a client, verify credentials, and return (client, user_id, user_name).
    Raises RuntimeError on auth failure.
    """
    client    = OpenProjectClient(base_url, api_key, insecure=insecure)
    me        = client.get_current_user()
    user_id   = me.get("id")
    user_name = me.get("name", "Unknown")
    if not user_id:
        raise RuntimeError("Could not determine user ID from /api/v3/users/me response.")
    return client, user_id, user_name


def _collect_one_entry(
    client: OpenProjectClient,
    user_id: int,
    # Cached lists from the session (avoids re-fetching every loop iteration)
    cached_projects:   Optional[List[dict]],
    cached_activities: Optional[List[dict]],
    # Special days loaded for this session
    session_special_days: Dict[date, Tuple[str, str]],
) -> Tuple[Optional[dict], Optional[List[dict]], Optional[List[dict]]]:
    """
    Interactively collect parameters for one time-entry batch.
    Returns (params_dict_or_None_if_cancelled, updated_projects_cache, updated_activities_cache).
    """
    from openproject.special_days.ui import _group_special_days_for_display

    # ── Projects ──────────────────────────────────────────────────────────────
    log_rule(_t("🌿 Project", "Project"))

    if cached_projects is None:
        _fetch_msg = _c(DIM, _t("🐒 Swinging to fetch your projects...", "Fetching your projects..."))
        print(f"  {_fetch_msg}", end="\r", flush=True)
        try:
            cached_projects = client.get_projects()
            print(" " * 40, end="\r")  # clear the fetching line
        except RuntimeError as e:
            print(" " * 40, end="\r")
            log_error(_t(f"🙊 Could not fetch projects: {e}", f"Could not fetch projects: {e}"))
            cached_projects = []

    project_id, project_name = _pick_from_api_list(
        label="project",
        items=cached_projects,
        name_key="name",
        id_extractor=lambda p: p.get("id"),
        fallback_prompt="Project ID",
    )

    # ── Work packages ─────────────────────────────────────────────────────────
    log_rule(_t("📦 Work Package", "Work Package"))

    _wp_msg = _c(DIM, _t("🐒 Grabbing work packages...", "Fetching work packages..."))
    print(f"  {_wp_msg}", end="\r", flush=True)
    try:
        work_packages = client.get_work_packages(project_id)
        print(" " * 40, end="\r")
    except RuntimeError as e:
        print(" " * 40, end="\r")
        log_error(_t(f"🙊 Could not fetch work packages: {e}", f"Could not fetch work packages: {e}"))
        work_packages = []

    wp_id, wp_name = _pick_from_api_list(
        label="work package",
        items=work_packages,
        name_key="subject",
        id_extractor=lambda wp: wp.get("id"),
        fallback_prompt="Work Package ID",
    )

    # ── Activities ────────────────────────────────────────────────────────────
    log_rule(_t("⚡ Activity", "Activity"))

    if cached_activities is None:
        _act_msg = _c(DIM, _t("🐒 Sniffing out activities...", "Fetching activities..."))
        print(f"  {_act_msg}", end="\r", flush=True)
        try:
            cached_activities = client.get_activities(
                project_id=project_id, work_package_id=wp_id, user_id=user_id
            )
            print(" " * 40, end="\r")
        except RuntimeError as e:
            print(" " * 40, end="\r")
            log_error(_t(f"🙊 Could not fetch activities: {e}", f"Could not fetch activities: {e}"))
            cached_activities = []

    activity_id, activity_name = _pick_from_api_list(
        label="activity",
        items=cached_activities,
        name_key="name",
        id_extractor=lambda a: _href_id(a.get("_links", {}).get("self", {}).get("href")),
        fallback_prompt="Activity ID",
        fallback_default=3,
    )

    # ── Hours & comment ───────────────────────────────────────────────────────
    log_rule(_t("⏰ Time", "Time"))

    hours   = prompt_float("Hours per day", default=8.0)
    comment = prompt("Comment", default="", required=False)

    # ── Dates ─────────────────────────────────────────────────────────────────
    log_rule(_t("📅 Dates", "Dates"))

    mode_idx = prompt_choice(
        "Date mode:",
        choices=["Single date", "Date range"],
        default=1,
    )

    today = date.today()

    if mode_idx == 1:
        single     = prompt_date("Date (YYYY-MM-DD)", default=today)
        candidates = [single]
    else:
        start = prompt_date("Start date (YYYY-MM-DD)")
        while True:
            end = prompt_date("End date   (YYYY-MM-DD)")
            if end >= start:
                break
            log_error(_t("🙊 End date must be on or after start date, monke!", "End date must be on or after start date."))
        candidates = date_range(start, end)

    # ── Special days strategy (upfront, if any fall in range) ─────────────────
    festive_activity_id:  Optional[int] = None
    vacation_activity_id: Optional[int] = None
    festives_in_range:  List[Tuple[date, str]] = []
    vacations_in_range: List[Tuple[date, str]] = []

    if session_special_days:
        candidates_set = set(candidates)
        for d, (day_type, day_name) in session_special_days.items():
            if d in candidates_set:
                if day_type == "festive":
                    festives_in_range.append((d, day_name))
                else:
                    vacations_in_range.append((d, day_name))

        if festives_in_range or vacations_in_range:
            log_rule(_t("🎉 Special Days in range", "Special Days in range"))

            if festives_in_range:
                print(f"\n  {_c(BOLD, 'Festives')}  ({len(festives_in_range)} day(s))")
                for rng, name, count in _group_special_days_for_display(festives_in_range):
                    suffix = f"  ({count}d)" if count > 1 else ""
                    print(f"    {_c(CYAN, rng):<36}  {name}{suffix}")

            if vacations_in_range:
                print(f"\n  {_c(BOLD, 'Vacations')}  ({len(vacations_in_range)} day(s))")
                for rng, name, count in _group_special_days_for_display(vacations_in_range):
                    suffix = f"  ({count}d)" if count > 1 else ""
                    print(f"    {_c(YELLOW, rng):<36}  {name}{suffix}")

            print()

            if festives_in_range:
                fest_choice = prompt_choice(
                    _t("🎉 Festive days — what to do?", "Festive days:"),
                    ["Skip them", "Use a different activity"],
                    default=1,
                )
                if fest_choice == 2:
                    festive_activity_id, _ = _pick_from_api_list(
                        label="activity for festives",
                        items=cached_activities or [],
                        name_key="name",
                        id_extractor=lambda a: _href_id(
                            a.get("_links", {}).get("self", {}).get("href")
                        ),
                        fallback_prompt="Activity ID for festives",
                        fallback_default=3,
                    )

            if vacations_in_range:
                vac_choice = prompt_choice(
                    _t("🏖 Vacation days — what to do?", "Vacation days:"),
                    ["Skip them", "Use a different activity"],
                    default=1,
                )
                if vac_choice == 2:
                    vacation_activity_id, _ = _pick_from_api_list(
                        label="activity for vacations",
                        items=cached_activities or [],
                        name_key="name",
                        id_extractor=lambda a: _href_id(
                            a.get("_links", {}).get("self", {}).get("href")
                        ),
                        fallback_prompt="Activity ID for vacations",
                        fallback_default=3,
                    )

    # ── Options ───────────────────────────────────────────────────────────────
    log_rule(_t("⚙️  Options", "Options"))

    dry_run = prompt_bool("Dry-run? (preview only, no entries created)", default=False)

    # ── Confirmation ──────────────────────────────────────────────────────────
    log_rule(_t("🐵 Confirm", "Confirm"))

    date_summary = (
        candidates[0].isoformat()
        if len(candidates) == 1
        else f"{candidates[0]} → {candidates[-1]}  ({len(candidates)} day(s))"
    )
    print()
    print(f"  {_t('Project', 'Project'):<18}: {project_name}  {_c(DIM, f'(#{project_id})')}")
    print(f"  {_t('Work Package', 'Work Package'):<18}: {wp_name}  {_c(DIM, f'(#{wp_id})')}")
    print(f"  {_t('Activity', 'Activity'):<18}: {activity_name}  {_c(DIM, f'(#{activity_id})')}")
    print(f"  {_t('Hours/day', 'Hours/day'):<18}: {hours}h")
    print(f"  {_t('Comment', 'Comment'):<18}: {comment or '(none)'}")
    print(f"  {_t('Dates', 'Dates'):<18}: {date_summary}")
    if festives_in_range:
        fest_label = (
            f"Activity #{festive_activity_id}"
            if festive_activity_id is not None
            else f"Skip ({len(festives_in_range)} day(s))"
        )
        print(f"  {_t('Festives', 'Festives'):<18}: {fest_label}")
    if vacations_in_range:
        vac_label = (
            f"Activity #{vacation_activity_id}"
            if vacation_activity_id is not None
            else f"Skip ({len(vacations_in_range)} day(s))"
        )
        print(f"  {_t('Vacations', 'Vacations'):<18}: {vac_label}")
    print(f"  {_t('Dry-run', 'Dry-run'):<18}: {'Yes ⚠' if dry_run else 'No'}")
    print()

    confirmed = prompt_bool("Proceed?", default=True)
    if not confirmed:
        _cancel_msg = _t(
            "🙉  Entry cancelled — swinging back to the tree.",
            "Entry cancelled — returning to menu.",
        )
        print(f"\n  {_cancel_msg}\n")
        return None, cached_projects, cached_activities

    return {
        "wp_id":                wp_id,
        "user_id":              user_id,
        "activity_id":          activity_id,
        "hours":                hours,
        "comment":              comment,
        "candidates":           candidates,
        "dry_run":              dry_run,
        "festive_activity_id":  festive_activity_id,
        "vacation_activity_id": vacation_activity_id,
    }, cached_projects, cached_activities


def interactive_mode(insecure: bool = False, special_days_file: Optional[str] = None) -> None:
    """
    Full interactive session:
      1. Collect credentials once and verify them.
      2. Optionally load a pre-provided special days file silently.
      3. Top-level hub menu:
           1) Log time entries
           2) Festives & vacations
           3) Exit
         Type 'exit' (or Ctrl+C) to leave the session.
    """
    import openproject.theme as _theme
    if _theme._MONKE:
        print(f"\n{_c(BOLD, '  ╔══════════════════════════════════════════════════════╗')}")
        print(f"{_c(BOLD,   '  ║   🐵  Monke Time Logger  ·  OpenProject v3  🍌       ║')}")
        print(f"{_c(BOLD,   '  ║       Log your hours. Earn your bananzas.  🐒        ║')}")
        print(f"{_c(BOLD,   '  ╚══════════════════════════════════════════════════════╝')}")
    else:
        print(f"\n{_c(BOLD, '  ╔══════════════════════════════════════════════════════╗')}")
        print(f"{_c(BOLD,   '  ║        OpenProject Time Entry Logger                 ║')}")
        print(f"{_c(BOLD,   '  ╚══════════════════════════════════════════════════════╝')}")
    _hint = _c(DIM, 'Type "exit" at any prompt to quit the session.')
    print(f"  {_hint}\n")

    # ── Connect (once per session) ────────────────────────────────────────────
    log_rule(_t("🔑 Connection", "Connection"))

    base_url = prompt(
        "Base URL",
        default=os.environ.get("OPENPROJECT_BASE_URL", ""),
    )

    env_key = os.environ.get("OPENPROJECT_API_KEY", "")
    if env_key:
        masked = "*" * min(len(env_key), 8)
        raw = prompt(f"API Key (press Enter to use env var [{_c(DIM, masked)}])",
                     default="__env__", required=False)
        api_key = env_key if (not raw or raw == "__env__") else raw
    else:
        api_key = prompt_secret("API Key (input hidden)")

    insecure_env     = os.environ.get("OPENPROJECT_INSECURE", "0").strip() == "1"
    insecure_default = insecure or insecure_env
    insecure = insecure_default or prompt_bool(
        "Skip SSL certificate verification? (use for self-signed certs)",
        default=insecure_env,
    )

    if insecure:
        log_error(_t("🙊 SSL verification disabled — proceed with caution, monke!", "Warning: SSL verification is disabled."))

    # Verify credentials and auto-detect user
    _conn_msg = _c(DIM, _t("🐒 Swinging to the server...", "Verifying credentials..."))
    print(f"\n  {_conn_msg}", end="\r", flush=True)
    try:
        client, user_id, user_name = _connect_and_identify(base_url, api_key, insecure=insecure)
        print(" " * 40, end="\r")
        _conn_label = _t("🍌 Connected as", "Connected as")
        log_ok(f"{_conn_label} {_c(BOLD, user_name)}  {_c(DIM, f'(user ID: {user_id})')}")
    except RuntimeError as e:
        print(" " * 40, end="\r")
        _auth_fail = _t(
            "🙈 Authentication failed — the server didn't let this monke in:",
            "Authentication failed:",
        )
        log_error(f"{_auth_fail} {e}")
        sys.exit(1)

    # ── Session state for special days ────────────────────────────────────────
    session_csv_path:     Optional[str]                   = None
    session_csv_entries:  Optional[List[SpecialDayEntry]] = None
    session_special_days: Dict[date, Tuple[str, str]]     = {}
    session_ics_path:     Optional[str]                   = None

    # If a special days file was pre-provided via CLI flag, load it silently
    if special_days_file is not None:
        try:
            entries = load_special_day_entries(special_days_file)
            session_special_days = expand_entries(entries)
            if special_days_file.lower().endswith(".csv"):
                session_csv_path    = special_days_file
                session_csv_entries = entries
            else:
                csv_path, merged_entries = ensure_csv_from_ics(special_days_file, entries)
                session_csv_path    = csv_path
                session_csv_entries = merged_entries
                session_ics_path    = special_days_file
                log_ok(_t(
                    f"Saved to CSV: {csv_path}",
                    f"Loaded from ICS — saved to CSV: {csv_path}",
                ))
            log_ok(
                _t(
                    f"Loaded {_c(BOLD, str(len(entries)))} special day entry/entries "
                    f"from {_c(BOLD, special_days_file)}",
                    f"Loaded {len(entries)} special day entry/entries "
                    f"from {special_days_file}",
                )
            )
        except (OSError, IOError, ValueError) as exc:
            log_error(_t(
                f"Could not load special days file: {exc}",
                f"Could not load special days file: {exc}"
            ))

    # ── Session loop ──────────────────────────────────────────────────────────
    cached_projects:   Optional[List[dict]] = None
    cached_activities: Optional[List[dict]] = None
    session_stats = {
        "created": 0,
        "skipped_weekend":  0,
        "skipped_existing": 0,
        "skipped_festive":  0,
        "skipped_vacation": 0,
        "failed": 0,
    }
    entry_count = 0

    # ── Outer loop: top-level hub menu ────────────────────────────────────────
    while True:
        log_rule(_t("🐵 What's next?", "Main menu"))
        print(f"  {_c(DIM, '─────────────────────────────────────────')}")
        print(f"    {_c(CYAN, '▸')} {_c(BOLD, '1')})  {_t('🍌 Log time entries', 'Log time entries')}")
        print(f"      {_c(BOLD, '2')})  {_t('📅 Festives & vacations', 'Festives & vacations')}")
        print(f"      {_c(BOLD, '3')})  {_t('🚪 Exit', 'Exit')}")
        print(f"  {_c(DIM, '─────────────────────────────────────────')}\n")

        try:
            raw_menu = prompt("Choice", default="1")
        except SystemExit:
            break

        if _is_exit(raw_menu) or raw_menu.strip() == "3":
            break

        elif raw_menu.strip() == "2":
            # ── Festives & vacations manager ──────────────────────────────────
            try:
                session_csv_path, session_csv_entries = _manage_special_days(
                    session_csv_path, session_csv_entries,
                    preset_ics_path=session_ics_path,
                )
                if session_csv_entries is not None:
                    session_special_days = expand_entries(session_csv_entries)
            except SystemExit:
                pass
            continue

        # ── Option 1: Log time entries (inner loop) ────────────────────────────
        while True:
            entry_count += 1
            log_divider()
            _entry_icon = _t("🐵 Entry #", "Entry #")
            _entry_hint = _c(DIM, '— type "exit" at any prompt to quit')
            print(f"  {_c(BOLD + CYAN, _entry_icon + str(entry_count))}  {_entry_hint}")

            try:
                params, cached_projects, cached_activities = _collect_one_entry(
                    client, user_id, cached_projects, cached_activities,
                    session_special_days,
                )
            except SystemExit:
                # Propagate exit all the way out
                entry_count -= 1  # don't count the cancelled entry
                break

            if params is None:
                # User cancelled this entry; decrement count and ask to retry
                entry_count -= 1
                try:
                    again = prompt_bool(
                        _t("🐵 Try another entry?", "Try another entry?"), default=True
                    )
                except SystemExit:
                    break
                if not again:
                    break
                continue

            # Run the logging loop
            _launch_label = _t(
                f"🐵 Launching entry #{entry_count} into the jungle...",
                f"OpenProject Time Entry Logger — entry #{entry_count}",
            )
            log_section(_launch_label)
            log_info(f"Base URL    : {base_url}")
            log_info(f"User        : {user_name}  (ID: {user_id})")
            log_info(f"Work Package: #{params['wp_id']}")
            log_info(f"Activity    : #{params['activity_id']}")
            log_info(f"Hours/day   : {params['hours']}h  →  {hours_to_iso8601(params['hours'])}")
            log_info(f"Dates       : {params['candidates'][0]} → {params['candidates'][-1]}"
                     f"  ({len(params['candidates'])} day(s))")

            stats = run(
                client=client,
                work_package_id=params["wp_id"],
                user_id=params["user_id"],
                activity_id=params["activity_id"],
                hours=params["hours"],
                comment=params["comment"],
                candidates=params["candidates"],
                dry_run=params["dry_run"],
                special_days=session_special_days,
                festive_activity_id=params.get("festive_activity_id"),
                vacation_activity_id=params.get("vacation_activity_id"),
            )
            print_summary(stats, params["dry_run"])

            if params["dry_run"] and stats["created"] > 0:
                try:
                    go_real = prompt_bool(
                        _t("🍌 Looks good — run for real?", "Looks good — execute for real?"),
                        default=True,
                    )
                except SystemExit:
                    # Accumulate before breaking
                    for k in session_stats:
                        session_stats[k] += stats.get(k, 0)
                    break
                if go_real:
                    stats = run(
                        client=client,
                        work_package_id=params["wp_id"],
                        user_id=params["user_id"],
                        activity_id=params["activity_id"],
                        hours=params["hours"],
                        comment=params["comment"],
                        candidates=params["candidates"],
                        dry_run=False,
                        special_days=session_special_days,
                        festive_activity_id=params.get("festive_activity_id"),
                        vacation_activity_id=params.get("vacation_activity_id"),
                    )
                    print_summary(stats, dry_run=False)

            # Accumulate session totals (use final stats — real run if promoted from dry-run)
            for k in session_stats:
                session_stats[k] += stats.get(k, 0)

            # ── Ask to log another entry or return to main menu ────────────────
            try:
                again = prompt_bool(
                    _t("🔁 Log another entry?", "Log another entry?"), default=True
                )
            except SystemExit:
                break
            if not again:
                break
            # else: inner loop continues → log another entry

    # ── Session summary ───────────────────────────────────────────────────────
    if entry_count > 1:
        log_section(_t(
            "🍌 Session Bananza Report (all entries combined):",
            "Session Summary (all entries combined):",
        ))
        print(f"  {_t('🍌', _c(GREEN, '✔'))}  Logged              : {session_stats['created']}")
        print(f"  {_t('🌴', _c(YELLOW, '⏭'))}  Skipped (weekend)   : {session_stats['skipped_weekend']}")
        print(f"  {_t('🙈', _c(YELLOW, '⏭'))}  Skipped (existing)  : {session_stats['skipped_existing']}")
        if session_stats.get("skipped_festive"):
            print(f"  {_t('🎉', _c(YELLOW, '⏭'))}  Skipped (festive)   : {session_stats['skipped_festive']}")
        if session_stats.get("skipped_vacation"):
            print(f"  {_t('🏖', _c(YELLOW, '⏭'))}  Skipped (vacation)  : {session_stats['skipped_vacation']}")
        if session_stats["failed"]:
            print(f"  {_t('🙊', _c(RED, '✘'))}  Failed              : {session_stats['failed']}")

    print(f"\n  {_t('🐵  All bananzas logged! See you next swing, monke! 🍌🍌🍌', 'Session ended. See you next time!')}\n")

    if session_stats["failed"]:
        sys.exit(1)
