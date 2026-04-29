"""Display helpers and interactive manager for special days."""
import csv
import os
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from openproject.special_days.model import SpecialDayEntry
from openproject.special_days.io import (
    _load_ics_entries,
    _load_csv_entries,
    save_csv_entries,
    compare_entries,
)
from openproject.theme import (
    _t, _c,
    GREEN, YELLOW, CYAN, BOLD, DIM,
    log_ok, log_skip, log_error, log_info, log_rule,
)
from openproject.prompts import prompt, prompt_bool, prompt_choice, prompt_date
from openproject.dates import date_range


# ── Display helpers ────────────────────────────────────────────────────────────

def _fmt_range(entry: SpecialDayEntry) -> str:
    """Human-readable date range for a SpecialDayEntry."""
    if entry.start == entry.end:
        return entry.start.isoformat()
    return f"{entry.start.isoformat()} → {entry.end.strftime('%m-%d')}"


def _print_numbered_entries(entries: List[SpecialDayEntry]) -> None:
    """Print a numbered list of entries for edit/remove menus."""
    for i, e in enumerate(entries, 1):
        type_color = CYAN if e.type == "festive" else YELLOW
        type_label = _c(type_color, f"{e.type:<10}")
        print(f"    {_c(BOLD, str(i))})  {_fmt_range(e):<28}  {type_label}  {e.name}")


def _view_entries(entries: List[SpecialDayEntry]) -> None:
    """Display all entries grouped by type."""
    if not entries:
        log_skip(_t("No special days yet, monke!", "No entries."))
        return
    log_rule(_t("📅 All special days", "All special days"))
    festives  = [e for e in entries if e.type == "festive"]
    vacations = [e for e in entries if e.type == "vacation"]
    if festives:
        print(f"\n  {_c(BOLD, 'Festives')}  ({len(festives)})")
        for e in festives:
            print(f"    {_c(CYAN, _fmt_range(e)):<36}  {e.name}")
    if vacations:
        print(f"\n  {_c(BOLD, 'Vacations')}  ({len(vacations)})")
        for e in vacations:
            print(f"    {_c(YELLOW, _fmt_range(e)):<36}  {e.name}")
    print()


def _group_special_days_for_display(
    days: List[Tuple[date, str]],
) -> List[Tuple[str, str, int]]:
    """
    Collapse consecutive days with the same name into compact range strings.
    Returns list of (range_str, name, count).
    """
    if not days:
        return []
    sorted_days = sorted(days, key=lambda x: x[0])
    groups: List[Tuple[str, str, int]] = []
    start_d, name = sorted_days[0]
    end_d, count  = start_d, 1

    for d, n in sorted_days[1:]:
        if n == name and d == end_d + timedelta(days=1):
            end_d  = d
            count += 1
        else:
            rng = start_d.isoformat() if start_d == end_d else f"{start_d.isoformat()} → {end_d.strftime('%m-%d')}"
            groups.append((rng, name, count))
            start_d, name, end_d, count = d, n, d, 1

    rng = start_d.isoformat() if start_d == end_d else f"{start_d.isoformat()} → {end_d.strftime('%m-%d')}"
    groups.append((rng, name, count))
    return groups


# ── Manager helpers ────────────────────────────────────────────────────────────

def _add_entry_interactive() -> Optional[SpecialDayEntry]:
    """Interactively collect data for a new SpecialDayEntry."""
    log_rule(_t("➕ Add special day", "Add entry"))

    type_idx   = prompt_choice("Type:", ["Festive", "Vacation"], default=1)
    entry_type = "festive" if type_idx == 1 else "vacation"

    start = prompt_date("Start date (YYYY-MM-DD)")

    end_raw = prompt(
        "End date   (YYYY-MM-DD)",
        default=start.isoformat(),
        required=False,
    )
    try:
        end = date.fromisoformat(end_raw) if end_raw else start
    except ValueError:
        log_error(_t("🙊 Invalid end date — using start date, monke!", "Invalid end date — using start date."))
        end = start

    if end < start:
        log_error(_t("🙊 End date is before start date — using start date, monke!", "End date is before start date — using start date."))
        end = start

    name = prompt("Name / description")

    days = (end - start).days + 1
    preview = SpecialDayEntry(start=start, end=end, type=entry_type, name=name)
    log_info(_t(f"→ {_fmt_range(preview)}  {entry_type}  {name}  ({days} day(s))", f"→ {_fmt_range(preview)}  {entry_type}  {name}  ({days} day(s))"))

    if not prompt_bool("Confirm?", default=True):
        return None
    return preview


def _edit_entry_interactive(
    entries: List[SpecialDayEntry],
) -> Optional[List[SpecialDayEntry]]:
    """Prompt to pick and edit one entry. Returns updated list or None if cancelled."""
    if not entries:
        log_skip(_t("Nothing to edit, monke!", "No entries to edit."))
        return None

    log_rule(_t("✏️  Edit entry", "Edit entry"))
    _print_numbered_entries(entries)

    try:
        idx = int(prompt("Entry to edit (0 to cancel)", default="0")) - 1
    except ValueError:
        return None
    if not (0 <= idx < len(entries)):
        return None

    orig = entries[idx]
    log_info(_t(f"🖊  Editing: {_fmt_range(orig)}  {orig.type}  {orig.name}", f"Editing: {_fmt_range(orig)}  {orig.type}  {orig.name}"))
    print(f"  {_c(DIM, '(Press Enter to keep current value)')}\n")

    raw_type = prompt(f"Type [{orig.type}]", default=orig.type, required=False).strip().lower()
    entry_type = raw_type if raw_type in ("festive", "vacation") else orig.type

    raw_start = prompt(f"Start date [{orig.start.isoformat()}]", default=orig.start.isoformat(), required=False)
    try:
        start = date.fromisoformat(raw_start) if raw_start else orig.start
    except ValueError:
        log_error(_t("🙊 Invalid date — keeping original, monke!", "Invalid date — keeping original."))
        start = orig.start

    raw_end = prompt(f"End date   [{orig.end.isoformat()}]", default=orig.end.isoformat(), required=False)
    try:
        end = date.fromisoformat(raw_end) if raw_end else orig.end
    except ValueError:
        log_error(_t("🙊 Invalid date — keeping original, monke!", "Invalid date — keeping original."))
        end = orig.end

    if end < start:
        log_error(_t("🙊 End date before start — keeping original end, monke!", "End date before start — keeping original end."))
        end = orig.end

    raw_name = prompt(f"Name [{orig.name}]", default=orig.name, required=False)
    name = raw_name if raw_name else orig.name

    updated = SpecialDayEntry(start=start, end=end, type=entry_type, name=name)
    log_info(_t(f"→ Updated: {_fmt_range(updated)}  {entry_type}  {name}", f"→ Updated: {_fmt_range(updated)}  {entry_type}  {name}"))

    if not prompt_bool("Confirm?", default=True):
        return None

    result    = list(entries)
    result[idx] = updated
    return sorted(result, key=lambda e: (e.start, e.end))


def _remove_entry_interactive(
    entries: List[SpecialDayEntry],
) -> Optional[List[SpecialDayEntry]]:
    """Prompt to pick and remove one entry. Returns updated list or None if cancelled."""
    if not entries:
        log_skip(_t("Nothing to remove, monke!", "No entries to remove."))
        return None

    log_rule(_t("🗑  Remove entry", "Remove entry"))
    _print_numbered_entries(entries)

    try:
        idx = int(prompt("Entry to remove (0 to cancel)", default="0")) - 1
    except ValueError:
        return None
    if not (0 <= idx < len(entries)):
        return None

    entry = entries[idx]
    log_info(_t(f"🗑  Remove: {_fmt_range(entry)}  {entry.type}  {entry.name}", f"Remove: {_fmt_range(entry)}  {entry.type}  {entry.name}"))
    if not prompt_bool("Confirm?", default=True):
        return None

    return [e for i, e in enumerate(entries) if i != idx]


def _import_from_ics(
    csv_path: str,
    csv_entries: List[SpecialDayEntry],
    preset_ics_path: Optional[str] = None,
) -> Tuple[List[SpecialDayEntry], bool]:
    """
    Interactive ICS → CSV import with diff display.
    Auto-saves to csv_path on any change.
    Returns (updated_entries, was_modified).
    """
    log_rule(_t("📥 Import from ICS", "Import from ICS"))

    ics_path = preset_ics_path or prompt("ICS file path")

    try:
        print(f"  {_c(DIM, _t('🐒 Parsing ICS...', 'Parsing ICS file...'))}",
              end="\r", flush=True)
        ics_entries = _load_ics_entries(ics_path)
        print(" " * 50, end="\r")
    except (OSError, IOError) as exc:
        log_error(_t(f"🙊 Could not read ICS file: {exc}", f"Could not read ICS file: {exc}"))
        return csv_entries, False

    if not ics_entries:
        log_skip(_t("🙈 No events found in the ICS, monke!", "No events found in ICS file."))
        return csv_entries, False

    print(f"  Found {_c(BOLD, str(len(ics_entries)))} event(s) in ICS.")

    diff = compare_entries(ics_entries, csv_entries)

    # ── New entries ───────────────────────────────────────────────────────────
    if diff["new"]:
        log_rule(_t("🆕 New (not in CSV)", "New (not in CSV)"))
        for i, e in enumerate(diff["new"], 1):
            print(f"    {_c(BOLD, str(i))})  {_fmt_range(e):<28}  {e.type:<10}  {e.name}")

    # ── Conflicts ─────────────────────────────────────────────────────────────
    conflict_resolutions: Dict[int, int] = {}
    if diff["conflicts"]:
        log_rule(_t("⚠️  Conflicts (same dates, different name/type)", "Conflicts"))
        for i, (ics_e, csv_e) in enumerate(diff["conflicts"]):
            print(f"    {_c(BOLD, str(i + 1))})  {_fmt_range(ics_e)}")
            print(f"         CSV: {_c(YELLOW, f'{csv_e.type:<10}')}  {csv_e.name}")
            print(f"         ICS: {_c(CYAN,   f'{ics_e.type:<10}')}  {ics_e.name}")
            keep = prompt_choice(f"  Keep for {_fmt_range(ics_e)}:", ["Keep CSV", "Use ICS"], default=1)
            conflict_resolutions[i] = keep  # 1 = CSV, 2 = ICS

    # ── Already in CSV ────────────────────────────────────────────────────────
    if diff["existing"]:
        log_rule(_t("✅ Already in CSV (no change)", "Already in CSV (no change)"))
        for e in diff["existing"]:
            print(f"    {_c(GREEN, '✔')}  {_fmt_range(e):<28}  {e.name}")

    # ── CSV-only entries ──────────────────────────────────────────────────────
    if diff["csv_only"]:
        log_rule(_t("📌 Only in CSV (untouched)", "Only in CSV (untouched)"))
        for e in diff["csv_only"]:
            print(f"    {_c(GREEN, '✔')}  {_fmt_range(e):<28}  {e.name}")

    if not diff["new"] and not diff["conflicts"]:
        log_ok(_t("🍌 CSV is already up to date!", "CSV is already up to date with the ICS file."))
        return csv_entries, False

    # ── Select new entries to import ──────────────────────────────────────────
    selected_new: List[SpecialDayEntry] = []
    if diff["new"]:
        print()
        import_choice = prompt_choice(
            "Import new entries?",
            ["All new entries", "Select entries", "None"],
            default=1,
        )
        if import_choice == 1:
            selected_new = list(diff["new"])
        elif import_choice == 2:
            print(f"  Enter entry numbers to import (comma-separated, e.g. 1,3):")
            while True:
                raw = prompt("Entries", required=False)
                if not raw:
                    break
                try:
                    indices    = [int(x.strip()) - 1 for x in raw.split(",")]
                    selected_new = [diff["new"][i] for i in indices if 0 <= i < len(diff["new"])]
                    break
                except (ValueError, IndexError):
                    log_error(f"Invalid selection. Enter numbers 1–{len(diff['new'])}.")

    # ── Build updated list ────────────────────────────────────────────────────
    updated = list(csv_entries)

    # Apply conflict resolutions
    for i, (ics_e, csv_e) in enumerate(diff["conflicts"]):
        if conflict_resolutions.get(i, 1) == 2:   # use ICS version
            updated = [e for e in updated if not (e.start == csv_e.start and e.end == csv_e.end)]
            updated.append(ics_e)

    # Add newly imported entries
    updated.extend(selected_new)

    was_modified = bool(selected_new) or any(v == 2 for v in conflict_resolutions.values())

    if was_modified:
        updated = sorted(updated, key=lambda e: (e.start, e.end))
        save_csv_entries(csv_path, updated)
        log_ok(_t("🍌 Imported and auto-saved!", "Imported and saved."))

    return updated, was_modified


def _manage_special_days(
    csv_path:    Optional[str],
    csv_entries: Optional[List[SpecialDayEntry]],
    preset_ics_path: Optional[str] = None,
) -> Tuple[Optional[str], Optional[List[SpecialDayEntry]]]:
    """
    Full interactive file manager for special days.
    Auto-saves on every modification (add / edit / remove / import).
    Returns (csv_path, entries).
    """
    # Ask for path upfront if we don't have one yet
    if csv_path is None:
        log_rule(_t("📅 Special Days Manager", "Special Days Manager"))
        print(f"  {_c(DIM, 'Enter a path to create or open a CSV file.')}")
        csv_path = prompt("CSV file path", default="festives.csv")

    # Load entries if the file exists and we don't have them in memory yet
    if csv_entries is None:
        if os.path.isfile(csv_path):
            try:
                csv_entries = _load_csv_entries(csv_path)
                log_ok(f"Loaded {len(csv_entries)} entry/entries from {_c(BOLD, csv_path)}")
            except (OSError, IOError, csv.Error) as exc:
                log_error(_t(f"🙊 Could not load {csv_path}: {exc}", f"Could not load {csv_path}: {exc}"))
                csv_entries = []
        else:
            csv_entries = []
            print(f"  {_c(DIM, _t('🐒 New file — no entries yet.', 'New file — no entries yet.'))}")

    while True:
        print()
        _header    = _t("🐵 Special Days Manager", "Special Days Manager")
        file_label = f"{_c(BOLD, csv_path)}  ({len(csv_entries)} entries)"
        log_rule(_header)
        print(f"  File: {file_label}")

        idx = prompt_choice(
            "What would you like to do?",
            [
                _t("👀 View all entries",             "View all entries"),
                _t("➕ Add entry",                    "Add entry"),
                _t("✏️  Edit entry",                  "Edit entry"),
                _t("🗑  Remove entry",                "Remove entry"),
                _t("📥 Import from ICS",              "Import from ICS"),
                _t("💾 Save As...",                   "Save As..."),
                _t("🌴 Close (back to session)",      "Close (back to session)"),
            ],
            default=1,
        )

        if idx == 1:    # View
            _view_entries(csv_entries)

        elif idx == 2:  # Add
            new_entry = _add_entry_interactive()
            if new_entry:
                csv_entries.append(new_entry)
                csv_entries = sorted(csv_entries, key=lambda e: (e.start, e.end))
                save_csv_entries(csv_path, csv_entries)
                log_ok(_t("🍌 Added and auto-saved!", "Added and saved."))

        elif idx == 3:  # Edit
            updated = _edit_entry_interactive(csv_entries)
            if updated is not None:
                csv_entries = updated
                save_csv_entries(csv_path, csv_entries)
                log_ok(_t("🍌 Updated and auto-saved!", "Updated and saved."))

        elif idx == 4:  # Remove
            updated = _remove_entry_interactive(csv_entries)
            if updated is not None:
                csv_entries = updated
                save_csv_entries(csv_path, csv_entries)
                log_ok(_t("🍌 Removed and auto-saved!", "Removed and saved."))

        elif idx == 5:  # Import from ICS
            csv_entries, _ = _import_from_ics(csv_path, csv_entries, preset_ics_path)

        elif idx == 6:  # Save As
            new_path = prompt("New file path", default=csv_path)
            save_csv_entries(new_path, csv_entries)
            csv_path = new_path
            log_ok(f"Saved to {_c(BOLD, csv_path)}")

        elif idx == 7:  # Close
            break

    return csv_path, csv_entries
