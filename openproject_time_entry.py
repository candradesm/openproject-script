#!/usr/bin/env python3
"""
OpenProject Time Entry Script
==============================
Logs time entries for a given date or date range via the OpenProject API v3.

Modes:
  Interactive  — run with no arguments; guided session with menus and a loop
                 so you can log multiple entries without re-entering credentials.
  Flag-based   — pass all values as CLI flags (scriptable / CI-friendly).

Features:
  - Fetches your projects, work packages, and activities from the API (no IDs to memorise)
  - Auto-detects your user ID from the API key
  - Session loop: keep logging entries until you type 'exit' or press Ctrl+C
  - Skip weekends automatically
  - Skip dates that already have a time entry
  - Dry-run mode to preview without creating anything
  - Zero external dependencies (stdlib only)

Authentication:
  Uses OpenProject API key via HTTP Basic Auth (apikey:<token>).
  Get your API key from: My Account → Access tokens → API

Flag-based usage examples:
  # Single date
  python3 openproject_time_entry.py \\
    --base-url https://openproject.napptilus.com \\
    --api-key YOUR_API_KEY \\
    --work-package-id 1296 \\
    --user-id 137 \\
    --date 2026-03-12

  # Date range
  python3 openproject_time_entry.py \\
    --base-url https://openproject.napptilus.com \\
    --api-key YOUR_API_KEY \\
    --work-package-id 1296 \\
    --user-id 137 \\
    --start-date 2026-03-01 \\
    --end-date 2026-03-31 \\
    --hours 8 \\
    --activity-id 3 \\
    --comment "Development work"

  # Dry-run preview
  python3 openproject_time_entry.py ... --dry-run

  # Environment variables (also pre-fill interactive prompts):
  export OPENPROJECT_BASE_URL=https://openproject.napptilus.com
  export OPENPROJECT_API_KEY=your_token_here
"""

import argparse
import base64
import getpass
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from typing import List, Optional, Tuple

# ── Theme toggle ───────────────────────────────────────────────────────────────
_MONKE: bool = os.environ.get("MONKE_THEME", "0").strip() == "1"

def _t(fun: str, plain: str) -> str:
    """Return the fun (monkey-themed) string or the plain string based on _MONKE."""
    return fun if _MONKE else plain

# ── Terminal colors ────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

def _c(color: str, text: str) -> str:
    return f"{color}{text}{RESET}"

def log_info(msg: str):    print(f"  {_t('🐵', _c(BLUE, 'ℹ'))}  {msg}")
def log_ok(msg: str):      print(f"  {_t('🍌', _c(GREEN, '✔'))}  {msg}")
def log_skip(msg: str):    print(f"  {_t('🙈', _c(YELLOW, '⏭'))}  {msg}")
def log_error(msg: str):   print(f"  {_t('🙊', _c(RED, '✘'))}  {_c(RED, msg)}", file=sys.stderr)
def log_dry(msg: str):     print(f"  {_t('🐒', _c(CYAN, '~'))}  {_c(CYAN, '[DRY-RUN]')} {msg}")
def log_section(msg: str): print(f"\n{_c(BOLD, msg)}")
def log_rule(label: str = ""):
    line = f"── {label} " if label else "──"
    print(f"\n  {_c(DIM, line + '─' * max(0, 48 - len(line)))}")
def log_divider():
    print(f"  {_c(DIM, '─' * 52)}")


# ── Interactive prompt helpers ─────────────────────────────────────────────────

def prompt(question: str, default: str = "", required: bool = True) -> str:
    """Prompt with optional default; repeat until non-empty when required."""
    hint = f" [{_c(DIM, default)}]" if default else ""
    while True:
        try:
            value = input(f"  {question}{hint}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)
        if value:
            return value
        if default:
            return default
        if not required:
            return ""
        print(f"  {_t('🙊', _c(RED, '✘'))}  {_t('This field is required, monke!', 'This field is required.')}")


def prompt_secret(question: str) -> str:
    """Prompt for a sensitive value (input not echoed)."""
    while True:
        try:
            value = getpass.getpass(f"  {question}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)
        if value:
            return value
        print(f"  {_t('🙊', _c(RED, '✘'))}  {_t('This field is required, monke!', 'This field is required.')}")


def prompt_int(question: str, default: Optional[int] = None, min_val: int = 1) -> int:
    """Prompt for a positive integer with optional default."""
    default_str = str(default) if default is not None else ""
    while True:
        raw = prompt(question, default=default_str, required=(default is None))
        try:
            value = int(raw)
            if value < min_val:
                raise ValueError()
            return value
        except ValueError:
            print(f"  {_t('🙊', _c(RED, '✘'))}  {_t(f'Enter a whole number ≥ {min_val}, monke!', f'Enter a whole number ≥ {min_val}.')}")


def prompt_float(question: str, default: float = 8.0) -> float:
    """Prompt for a positive float with a default."""
    while True:
        raw = prompt(question, default=str(default))
        try:
            value = float(raw)
            if value <= 0:
                raise ValueError()
            return value
        except ValueError:
            _pos_err = _t(
                "That's not a positive number, monke! Try something like 8 or 7.5.",
                "Enter a positive number (e.g. 8 or 7.5).",
            )
            print(f"  {_t('🙊', _c(RED, '✘'))}  {_pos_err}")


def prompt_date(question: str, default: Optional[date] = None) -> date:
    """Prompt for a YYYY-MM-DD date with optional default."""
    default_str = default.isoformat() if default else ""
    while True:
        raw = prompt(question, default=default_str, required=(default is None))
        try:
            return date.fromisoformat(raw)
        except ValueError:
            _date_err = _t(
                f"Invalid date '{raw}', monke! Use YYYY-MM-DD (e.g. 2026-03-12).",
                f"Invalid date '{raw}'. Use YYYY-MM-DD.",
            )
            print(f"  {_t('🙊', _c(RED, '✘'))}  {_date_err}")


def prompt_choice(question: str, choices: List[str], default: int = 1) -> int:
    """Show a numbered menu; return the 1-based index of the chosen option."""
    print(f"\n  {question}")
    for i, label in enumerate(choices, start=1):
        marker = _c(CYAN, "▸") if i == default else " "
        print(f"    {marker} {_c(BOLD, str(i))}) {label}")
    print()
    while True:
        raw = prompt("Choice", default=str(default))
        # Allow "exit" to propagate upward
        if raw.lower() in ("exit", "quit", "q"):
            raise SystemExit(0)
        try:
            idx = int(raw)
            if 1 <= idx <= len(choices):
                return idx
        except ValueError:
            pass
        _choice_err = _t(
            f"Pick a number between 1 and {len(choices)}, monke!",
            f"Enter a number between 1 and {len(choices)}.",
        )
        print(f"  {_t('🙊', _c(RED, '✘'))}  {_choice_err}")


def prompt_bool(question: str, default: bool = False) -> bool:
    """Prompt for a yes/no answer."""
    hint = "Y/n" if default else "y/N"
    raw = prompt(question, default=hint, required=False)
    if not raw or raw.lower() == hint.lower():
        return default
    return raw.lower() in ("y", "yes", "1", "true")


def _is_exit(value: str) -> bool:
    return value.strip().lower() in ("exit", "quit", "q", "bye")


# ── Date utilities ─────────────────────────────────────────────────────────────

def parse_date_arg(value: str) -> date:
    """argparse type converter for YYYY-MM-DD dates."""
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid date format '{value}'. Expected YYYY-MM-DD (e.g. 2026-03-12)."
        )


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5


def date_range(start: date, end: date) -> List[date]:
    result, current = [], start
    while current <= end:
        result.append(current)
        current += timedelta(days=1)
    return result


def hours_to_iso8601(hours: float) -> str:
    total_minutes = int(hours * 60)
    h, m = divmod(total_minutes, 60)
    return f"PT{h}H{m}M" if m else f"PT{h}H"


def _parse_iso_duration(duration: str) -> float:
    s = duration.upper()
    if s.startswith("PT"):
        s = s[2:]
    hours, minutes = 0.0, 0.0
    if "H" in s:
        h_parts = s.split("H", 1)
        hours = float(h_parts[0])
        s = h_parts[1]
    if "M" in s:
        minutes = float(s.split("M", 1)[0])
    return hours + minutes / 60.0


# ── OpenProject API client ─────────────────────────────────────────────────────

class OpenProjectClient:
    """Minimal OpenProject API v3 client (stdlib only)."""

    def __init__(self, base_url: str, api_key: str, insecure: bool = False):
        self.base_url = base_url.rstrip("/")
        self._insecure = insecure
        credentials = base64.b64encode(f"apikey:{api_key}".encode()).decode()
        self._auth_header = f"Basic {credentials}"

    def _request(self, method: str, path: str, body: Optional[dict] = None) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {
            "Authorization": self._auth_header,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        ssl_ctx: Optional[ssl.SSLContext] = None
        if self._insecure:
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
        try:
            with urllib.request.urlopen(req, context=ssl_ctx) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
                message = payload.get("message") or payload.get("error") or raw
            except json.JSONDecodeError:
                message = raw
            raise RuntimeError(
                f"HTTP {e.code} {e.reason} → {message}"
            ) from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Connection error: {e.reason}") from e

    # ── Identity ──────────────────────────────────────────────────────────────

    def get_current_user(self) -> dict:
        """Return the user resource for the authenticated API key."""
        return self._request("GET", "/api/v3/users/me")

    # ── Projects ──────────────────────────────────────────────────────────────

    def get_projects(self) -> List[dict]:
        """Return all projects the current user is a member of."""
        params = urllib.parse.urlencode({
            "pageSize": 200,
            "sortBy": '[["name","asc"]]',
        })
        result = self._request("GET", f"/api/v3/projects?{params}")
        return result.get("_embedded", {}).get("elements", [])

    # ── Work packages ─────────────────────────────────────────────────────────

    def get_work_packages(self, project_id: int) -> List[dict]:
        """Return open work packages for a given project, sorted by ID desc."""
        filters = json.dumps([
            {"project_id": {"operator": "=", "values": [str(project_id)]}},
            {"status":     {"operator": "o"}},           # 'o' = open
        ])
        params = urllib.parse.urlencode({
            "filters":  filters,
            "pageSize": 100,
            "sortBy":   '[["id","desc"]]',
        })
        result = self._request("GET", f"/api/v3/work_packages?{params}")
        return result.get("_embedded", {}).get("elements", [])

    # ── Activities ────────────────────────────────────────────────────────────

    def get_activities(
        self,
        project_id: Optional[int] = None,
        work_package_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> List[dict]:
        """Return available time entry activities.

        Strategy:
          1. Try the dedicated endpoint with project_id / work_package_id / no param.
          2. If every attempt returns 400, fall back to extracting unique activities
             from the user's own recent time entries (guaranteed to work if any exist).
        """
        attempts = []
        if project_id is not None:
            attempts.append(f"/api/v3/time_entries/activities?project_id={project_id}")
        if work_package_id is not None:
            attempts.append(f"/api/v3/time_entries/activities?work_package_id={work_package_id}")
        attempts.append("/api/v3/time_entries/activities")

        for path in attempts:
            try:
                result = self._request("GET", path)
                elements = result.get("_embedded", {}).get("elements", [])
                if elements:
                    return elements
            except RuntimeError:
                continue

        # Dedicated endpoint unavailable — extract from existing time entries
        return self._activities_from_time_entries(user_id)

    def _activities_from_time_entries(self, user_id: Optional[int] = None) -> List[dict]:
        """
        Extract unique activities from the user's recent time entries.
        Each activity link in a time entry response includes href + title, which
        is enough to build a picker list.
        """
        params_dict = {"pageSize": 100, "sortBy": '[["spentOn","desc"]]'}
        if user_id is not None:
            params_dict["filters"] = json.dumps(
                [{"user_id": {"operator": "=", "values": [str(user_id)]}}]
            )
        params = urllib.parse.urlencode(params_dict)
        try:
            result = self._request("GET", f"/api/v3/time_entries?{params}")
        except RuntimeError:
            return []

        entries = result.get("_embedded", {}).get("elements", [])
        seen: set = set()
        activities: List[dict] = []
        for entry in entries:
            link = entry.get("_links", {}).get("activity", {})
            href = link.get("href", "")
            title = link.get("title", "")
            if href and href not in seen:
                seen.add(href)
                activities.append({
                    "name": title or href.split("/")[-1],
                    "_links": {"self": {"href": href}},
                })
        return activities

    # ── Time entries ──────────────────────────────────────────────────────────

    def get_existing_entries_for_date(self, user_id: int, spent_on: date) -> List[dict]:
        filters = json.dumps([
            {"spent_on": {"operator": "=d", "values": [spent_on.isoformat()]}},
            {"user_id":  {"operator": "=",  "values": [str(user_id)]}},
        ])
        params = urllib.parse.urlencode({"filters": filters, "pageSize": 50})
        result = self._request("GET", f"/api/v3/time_entries?{params}")
        return result.get("_embedded", {}).get("elements", [])

    def create_time_entry(
        self,
        work_package_id: int,
        user_id: int,
        activity_id: int,
        spent_on: date,
        hours: float,
        comment: str,
    ) -> dict:
        body = {
            "comment": {
                "format": "plain",
                "raw": comment,
                "html": f"<p>{comment}</p>" if comment else "",
            },
            "spentOn": spent_on.isoformat(),
            "hours": hours_to_iso8601(hours),
            "_links": {
                "workPackage": {"href": f"/api/v3/work_packages/{work_package_id}"},
                "user":        {"href": f"/api/v3/users/{user_id}"},
                "activity":    {"href": f"/api/v3/time_entries/activities/{activity_id}"},
                "self":        {"href": None},
            },
        }
        return self._request("POST", "/api/v3/time_entries", body)


# ── Core runner (shared by both modes) ────────────────────────────────────────

def run(
    client: OpenProjectClient,
    work_package_id: int,
    user_id: int,
    activity_id: int,
    hours: float,
    comment: str,
    candidates: List[date],
    dry_run: bool,
) -> dict:
    """
    Execute the time-entry logging loop for the given dates.
    Returns a stats dict so callers can inspect results.
    """
    if dry_run:
        _dry_msg = _t("DRY-RUN MODE — no bananzas will be created (yet).", "DRY-RUN — no entries will be created.")
        print(f"\n  {_t('🐒', '~')}  {_c(CYAN + BOLD, _dry_msg)}")

    stats = {"created": 0, "skipped_weekend": 0, "skipped_existing": 0, "failed": 0}

    log_section(_t("🍌 Processing dates:", "Processing dates:"))

    for d in candidates:
        date_str = d.isoformat()

        if is_weekend(d):
            _wknd = _t("🌴 weekend, this monke is chilling.", "weekend, skipping.")
            log_skip(f"{date_str}  ({d.strftime('%A')}) — {_wknd}")
            stats["skipped_weekend"] += 1
            continue

        try:
            existing = client.get_existing_entries_for_date(user_id, d)
        except RuntimeError as e:
            _chk_fail = _t("🙊 failed to check existing entries:", "failed to check existing entries:")
            log_error(f"{date_str} — {_chk_fail} {e}")
            stats["failed"] += 1
            continue

        if existing:
            total_h = sum(_parse_iso_duration(e.get("hours", "PT0H")) for e in existing)
            _already = _t("🙈 already has", "already has")
            log_skip(
                f"{date_str} — {_already} {len(existing)} entry/entries "
                f"({total_h:.1f}h total), skipping."
            )
            stats["skipped_existing"] += 1
            continue

        if dry_run:
            _would = _t("🍌 would log", "would log")
            log_dry(f"{date_str} — {_would} {hours}h on work package #{work_package_id}.")
            stats["created"] += 1
            continue

        try:
            created = client.create_time_entry(
                work_package_id=work_package_id,
                user_id=user_id,
                activity_id=activity_id,
                spent_on=d,
                hours=hours,
                comment=comment,
            )
            _logged = _t("🍌 bananza logged! Entry #", "created entry #")
            log_ok(f"{date_str} — {_logged}{created.get('id', '?')}  ({hours}h).")
            stats["created"] += 1
        except RuntimeError as e:
            _log_fail = _t("🙊 failed to log entry:", "failed to log entry:")
            log_error(f"{date_str} — {_log_fail} {e}")
            stats["failed"] += 1

    return stats


def print_summary(stats: dict, dry_run: bool):
    action_label = "Would log  " if dry_run else "Logged     "
    log_section(_t("🍌 Bananza Report:", "Summary:"))
    print(f"  {_t('🍌', _c(GREEN, '✔'))}  {action_label}      : {stats['created']}")
    print(f"  {_t('🌴', _c(YELLOW, '⏭'))}  Skipped (weekend)  : {stats['skipped_weekend']}")
    print(f"  {_t('🙈', _c(YELLOW, '⏭'))}  Skipped (existing) : {stats['skipped_existing']}")
    if stats["failed"]:
        print(f"  {_t('🙊', _c(RED, '✘'))}  Failed             : {stats['failed']}")
    print()


# ── Interactive mode: helpers ──────────────────────────────────────────────────

def _pick_from_api_list(
    label: str,
    items: List[dict],
    name_key: str,
    id_extractor,
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
        print(f"  {_t('🙈', _c(YELLOW, '⏭'))}  {_no_items}")
        item_id = prompt_int(fallback_prompt, default=fallback_default)
        return item_id, str(item_id)

    if len(items) == 1:
        chosen = items[0]
        item_id = id_extractor(chosen)
        item_name = chosen.get(name_key, str(item_id))
        _one_label = _t(
            f"🐵  Only one {label} available — auto-selected:",
            f"Only one {label} available — auto-selected:",
        )
        print(f"  {_one_label} "
              f"{_c(BOLD, item_name)}  {_c(DIM, f'(ID: {item_id})')}")
        return item_id, item_name

    labels = [
        f"{item.get(name_key, '?')}  {_c(DIM, f'(ID: {id_extractor(item)})')}"
        for item in items
    ]
    idx = prompt_choice(f"Select a {label}:", labels, default=1)
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
    client = OpenProjectClient(base_url, api_key, insecure=insecure)
    me = client.get_current_user()
    user_id = me.get("id")
    user_name = me.get("name", "Unknown")
    if not user_id:
        raise RuntimeError("Could not determine user ID from /api/v3/users/me response.")
    return client, user_id, user_name


# ── Interactive mode: one entry session ───────────────────────────────────────

def _collect_one_entry(
    client: OpenProjectClient,
    user_id: int,
    # Cached lists from the session (avoids re-fetching every loop iteration)
    cached_projects: Optional[List[dict]],
    cached_activities: Optional[List[dict]],
) -> Tuple[Optional[dict], Optional[List[dict]], Optional[List[dict]]]:
    """
    Interactively collect parameters for one time-entry batch.
    Returns (params_dict_or_None_if_cancelled, updated_projects_cache, updated_activities_cache).
    """

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
            log_error(f"Could not fetch projects: {e}")
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
        log_error(f"Could not fetch work packages: {e}")
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
            log_error(f"Could not fetch activities: {e}")
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
        single = prompt_date("Date (YYYY-MM-DD)", default=today)
        candidates = [single]
    else:
        start = prompt_date("Start date (YYYY-MM-DD)")
        while True:
            end = prompt_date("End date   (YYYY-MM-DD)")
            if end >= start:
                break
            print(f"  {_c(RED, '!')}  End date must be on or after {start}.")
        candidates = date_range(start, end)

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
    print(f"  {'Project':<16}: {project_name}  {_c(DIM, f'(#{project_id})')}")
    print(f"  {'Work Package':<16}: {wp_name}  {_c(DIM, f'(#{wp_id})')}")
    print(f"  {'Activity':<16}: {activity_name}  {_c(DIM, f'(#{activity_id})')}")
    print(f"  {'Hours/day':<16}: {hours}h")
    print(f"  {'Comment':<16}: {comment or '(none)'}")
    print(f"  {'Dates':<16}: {date_summary}")
    print(f"  {'Dry-run':<16}: {'Yes ⚠' if dry_run else 'No'}")
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
        "wp_id":        wp_id,
        "user_id":      user_id,
        "activity_id":  activity_id,
        "hours":        hours,
        "comment":      comment,
        "candidates":   candidates,
        "dry_run":      dry_run,
    }, cached_projects, cached_activities


# ── Interactive mode: session loop ────────────────────────────────────────────

def interactive_mode(insecure: bool = False):
    """
    Full interactive session:
      1. Collect credentials once and verify them.
      2. Loop: collect entry params → run → ask to continue.
         Type 'exit' (or Ctrl+C) to leave the loop.
    """
    if _MONKE:
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

    insecure_env = os.environ.get("OPENPROJECT_INSECURE", "0").strip() == "1"
    insecure_default = insecure or insecure_env
    insecure = insecure_default or prompt_bool(
        "Skip SSL certificate verification? (use for self-signed certs)",
        default=insecure_env,
    )

    if insecure:
        print(f"  {_c(YELLOW + BOLD, '⚠')}  {_c(YELLOW, 'SSL verification disabled — connection is not fully secure.')}")

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

    # ── Session loop ──────────────────────────────────────────────────────────
    cached_projects:    Optional[List[dict]] = None
    cached_activities:  Optional[List[dict]] = None
    session_stats = {"created": 0, "skipped_weekend": 0, "skipped_existing": 0, "failed": 0}
    entry_count = 0

    while True:
        entry_count += 1
        log_divider()
        _entry_icon = _t("🐵 Entry #", "Entry #")
        _entry_hint = _c(DIM, '— type "exit" at any prompt to quit')
        print(f"  {_c(BOLD + CYAN, _entry_icon + str(entry_count))}  {_entry_hint}")

        try:
            params, cached_projects, cached_activities = _collect_one_entry(
                client, user_id, cached_projects, cached_activities
            )
        except SystemExit:
            break

        if params is None:
            # User cancelled this entry; offer to try again or quit
            try:
                again = prompt_bool(_t("🐵 Start another entry?", "Start a new entry?"), default=True)
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
        )
        print_summary(stats, params["dry_run"])

        if params["dry_run"] and stats["created"] > 0:
            try:
                go_real = prompt_bool(
                    _t("🍌 Looks good — run for real?", "Looks good — execute for real?"),
                    default=True,
                )
            except SystemExit:
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
                )
                print_summary(stats, dry_run=False)

        # Accumulate session totals (use final stats — real run if promoted from dry-run)
        for k in session_stats:
            session_stats[k] += stats[k]

        # ── Continue prompt ───────────────────────────────────────────────────
        log_divider()
        print(f"\n  {_c(BOLD, _t('🐵 What next, monke?', 'What next?'))}")
        print(f"    {_c(CYAN, '▸')} {_c(BOLD, '1')}) {_t('🍌 Grab more bananzas (log another entry)', 'Log another entry')}")
        print(f"      {_c(BOLD, '2')}) {_t('🌴 Head to the jungle (quit)', 'Quit')}\n")
        try:
            raw = prompt("Choice", default="1")
        except SystemExit:
            break

        if _is_exit(raw) or raw.strip() == "2":
            break

    # ── Session summary ───────────────────────────────────────────────────────
    if entry_count > 1:
        log_section(_t(
            "🍌 Session Bananza Report (all entries combined):",
            "Session Summary (all entries combined):",
        ))
        print(f"  {_t('🍌', _c(GREEN, '✔'))}  Logged              : {session_stats['created']}")
        print(f"  {_t('🌴', _c(YELLOW, '⏭'))}  Skipped (weekend)   : {session_stats['skipped_weekend']}")
        print(f"  {_t('🙈', _c(YELLOW, '⏭'))}  Skipped (existing)  : {session_stats['skipped_existing']}")
        if session_stats["failed"]:
            print(f"  {_t('🙊', _c(RED, '✘'))}  Failed              : {session_stats['failed']}")

    print(f"\n  {_t('🐵  All bananzas logged! See you next swing, monke! 🍌🍌🍌', 'Session ended. See you next time!')}\n")

    if session_stats["failed"]:
        sys.exit(1)


# ── Flag-based mode ────────────────────────────────────────────────────────────

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Log time entries in OpenProject.\n"
            "Run with no arguments to start the interactive session."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    conn = parser.add_argument_group("Connection")
    conn.add_argument("--base-url", default=os.environ.get("OPENPROJECT_BASE_URL"),
                      metavar="URL",
                      help="Instance base URL (or set OPENPROJECT_BASE_URL env var).")
    conn.add_argument("--api-key",  default=os.environ.get("OPENPROJECT_API_KEY"),
                      metavar="TOKEN",
                      help="API access token (or set OPENPROJECT_API_KEY env var).")
    conn.add_argument("--insecure", action="store_true",
                      default=os.environ.get("OPENPROJECT_INSECURE", "0").strip() == "1",
                      help="Skip SSL certificate verification (for self-signed certs)."
                           " Or set OPENPROJECT_INSECURE=1.")

    entry = parser.add_argument_group("Time entry details")
    entry.add_argument("--work-package-id", type=int, default=None,   metavar="ID")
    entry.add_argument("--user-id",         type=int, default=None,   metavar="ID",
                       help="User ID. Auto-detected from API key if omitted.")
    entry.add_argument("--activity-id",     type=int, default=3,      metavar="ID")
    entry.add_argument("--hours",           type=float, default=8.0,  metavar="N")
    entry.add_argument("--comment",         default="",               metavar="TEXT")

    date_group = parser.add_argument_group("Date selection (choose one mode)")
    mode = date_group.add_mutually_exclusive_group(required=False)
    mode.add_argument("--date",       type=parse_date_arg, metavar="YYYY-MM-DD")
    mode.add_argument("--start-date", type=parse_date_arg, metavar="YYYY-MM-DD")
    parser.add_argument("--end-date", type=parse_date_arg, metavar="YYYY-MM-DD")

    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--monke", action="store_true",
        help="Enable monkey-themed output (or set MONKE_THEME=1).",
    )

    return parser


def validate_flag_args(args: argparse.Namespace, parser: argparse.ArgumentParser):
    if not args.base_url:
        parser.error("--base-url is required (or set OPENPROJECT_BASE_URL).")
    if not args.api_key:
        parser.error("--api-key is required (or set OPENPROJECT_API_KEY).")
    if args.work_package_id is None:
        parser.error("--work-package-id is required in flag mode.")
    if not args.date and not args.start_date:
        parser.error("--date or --start-date is required in flag mode.")
    if args.start_date and not args.end_date:
        parser.error("--end-date is required when --start-date is provided.")
    if args.end_date and not args.start_date:
        parser.error("--start-date is required when --end-date is provided.")
    if args.start_date and args.end_date and args.start_date > args.end_date:
        parser.error("--start-date must be ≤ --end-date.")
    if args.hours <= 0:
        parser.error("--hours must be a positive number.")


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    global _MONKE

    parser = build_arg_parser()
    args = parser.parse_args()

    _MONKE = _MONKE or args.monke

    if args.work_package_id is None:
        interactive_mode(insecure=args.insecure)
        return

    validate_flag_args(args, parser)

    # Resolve user ID (auto-detect if not provided)
    client = OpenProjectClient(args.base_url, args.api_key, insecure=args.insecure)
    user_id = args.user_id
    if user_id is None:
        try:
            me = client.get_current_user()
            user_id = me.get("id")
            if not user_id:
                raise RuntimeError("Empty user ID in response.")
            log_info(f"Auto-detected user: {me.get('name')}  (ID: {user_id})")
        except RuntimeError as e:
            print(f"Error: could not auto-detect user ID: {e}", file=sys.stderr)
            print("Provide --user-id explicitly.", file=sys.stderr)
            sys.exit(1)

    if args.date:
        candidates = [args.date]
    else:
        candidates = date_range(args.start_date, args.end_date)

    log_section(_t("🐵 Monke Time Logger — OpenProject API v3 🍌", "OpenProject Time Entry Logger"))
    if args.insecure:
        print(f"  {_c(YELLOW + BOLD, '⚠')}  {_c(YELLOW, 'SSL verification disabled — connection is not fully secure.')}")
    log_info(f"Base URL      : {args.base_url}")
    log_info(f"Work Package  : #{args.work_package_id}")
    log_info(f"User ID       : {user_id}")
    log_info(f"Activity ID   : {args.activity_id}")
    log_info(f"Hours/day     : {args.hours}h  →  {hours_to_iso8601(args.hours)}")
    log_info(f"Comment       : '{args.comment}'" if args.comment else "Comment       : (none)")
    log_info(f"Dates         : {candidates[0]} → {candidates[-1]}  ({len(candidates)} day(s))")

    stats = run(
        client=client,
        work_package_id=args.work_package_id,
        user_id=user_id,
        activity_id=args.activity_id,
        hours=args.hours,
        comment=args.comment,
        candidates=candidates,
        dry_run=args.dry_run,
    )
    print_summary(stats, args.dry_run)

    if args.dry_run and stats["created"] > 0:
        go_real = prompt_bool(
            _t("🍌 Looks good — run for real?", "Looks good — execute for real?"),
            default=True,
        )
        if go_real:
            stats = run(
                client=client,
                work_package_id=args.work_package_id,
                user_id=user_id,
                activity_id=args.activity_id,
                hours=args.hours,
                comment=args.comment,
                candidates=candidates,
                dry_run=False,
            )
            print_summary(stats, dry_run=False)

    if stats["failed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
