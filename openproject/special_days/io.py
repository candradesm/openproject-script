"""ICS/CSV loaders, savers, and helpers for special days."""
import csv
import os
import re
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from openproject.special_days.model import SpecialDayEntry


# ── ICS helpers ────────────────────────────────────────────────────────────────

def _ics_extract_date(block: str, property_name: str) -> Optional[date]:
    """
    Extract a date value from an ICS VEVENT block.
    Handles:
      DTSTART;VALUE=DATE:20260101
      DTSTART:20260101T000000Z
      DTSTART;TZID=Europe/Madrid:20260101T000000
    """
    pattern = re.compile(
        r'^' + re.escape(property_name) + r'(?:[;:][^:\r\n]*)?:(\d{8})',
        re.MULTILINE | re.IGNORECASE,
    )
    match = pattern.search(block)
    if not match:
        return None
    try:
        ds = match.group(1)
        return date(int(ds[:4]), int(ds[4:6]), int(ds[6:8]))
    except (ValueError, IndexError):
        return None


def _ics_extract_text(block: str, property_name: str) -> str:
    """Extract a text value from an ICS VEVENT block."""
    pattern = re.compile(
        r'^' + re.escape(property_name) + r'(?:[;:][^:\r\n]*)?:(.*?)$',
        re.MULTILINE | re.IGNORECASE,
    )
    match = pattern.search(block)
    if not match:
        return ""
    text = match.group(1).strip()
    # Unescape ICS text sequences
    text = re.sub(r'\\n', '\n', text)
    text = text.replace('\\;', ';').replace('\\,', ',').replace('\\\\', '\\')
    return text


# ── File loaders ───────────────────────────────────────────────────────────────

def _load_ics_entries(path: str) -> List[SpecialDayEntry]:
    """
    Parse an ICS file and return a list of SpecialDayEntry objects (read-only).

    Type detection via CATEGORIES field:
      CATEGORIES:VACATION  → vacation
      CATEGORIES:FESTIVE / CATEGORIES:HOLIDAY / absent → festive
    Multi-day events are preserved as a single entry (start/end range).
    """
    with open(path, encoding="utf-8", errors="replace") as f:
        content = f.read()

    # Unfold long lines (ICS line-folding: CRLF/LF + whitespace)
    content = re.sub(r'\r?\n[ \t]', '', content)

    entries: List[SpecialDayEntry] = []
    for match in re.finditer(r'BEGIN:VEVENT(.*?)END:VEVENT', content, re.DOTALL | re.IGNORECASE):
        block = match.group(1)

        dtstart = _ics_extract_date(block, 'DTSTART')
        if dtstart is None:
            continue

        dtend = _ics_extract_date(block, 'DTEND')
        if dtend is None or dtend <= dtstart:
            dtend = dtstart
        else:
            # DTEND is exclusive for all-day DATE events in ICS
            dtend = dtend - timedelta(days=1)

        summary    = _ics_extract_text(block, 'SUMMARY') or 'Special Day'
        categories = _ics_extract_text(block, 'CATEGORIES').lower()

        entry_type = 'festive'
        if 'vacation' in categories or 'time off' in categories or 'leave' in categories:
            entry_type = 'vacation'

        entries.append(SpecialDayEntry(start=dtstart, end=dtend, type=entry_type, name=summary))

    return entries


def _load_csv_entries(path: str) -> List[SpecialDayEntry]:
    """
    Parse a CSV file with columns: start_date, end_date, type, name.
    Skips malformed rows gracefully.
    """
    entries: List[SpecialDayEntry] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                start      = date.fromisoformat(row["start_date"].strip())
                end        = date.fromisoformat(row["end_date"].strip())
                entry_type = row["type"].strip().lower()
                name       = row["name"].strip()
                if entry_type not in ("festive", "vacation"):
                    entry_type = "festive"
                if end < start:
                    end = start
                entries.append(SpecialDayEntry(start=start, end=end, type=entry_type, name=name))
            except (KeyError, ValueError):
                continue
    return entries


def load_special_day_entries(path: str) -> List[SpecialDayEntry]:
    """
    Load special day entries from a CSV or ICS file (auto-detected by extension).
    CSV files are read/write; ICS files are read-only.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext == ".ics":
        return _load_ics_entries(path)
    elif ext == ".csv":
        return _load_csv_entries(path)
    else:
        # Unknown extension — try CSV first, then ICS
        try:
            return _load_csv_entries(path)
        except (OSError, IOError, csv.Error):
            return _load_ics_entries(path)


def save_csv_entries(path: str, entries: List[SpecialDayEntry]) -> None:
    """Write special day entries to a CSV file, sorted by start date."""
    sorted_entries = sorted(entries, key=lambda e: (e.start, e.end, e.type, e.name))
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["start_date", "end_date", "type", "name"])
        for entry in sorted_entries:
            writer.writerow([entry.start.isoformat(), entry.end.isoformat(), entry.type, entry.name])


def ensure_csv_from_ics(
    ics_path: str,
    ics_entries: List[SpecialDayEntry],
) -> Tuple[str, List[SpecialDayEntry]]:
    """Ensure a sibling CSV file exists and contains all entries from the ICS source.

    Derives the CSV path by replacing the ICS file's extension with '.csv'.
    Loads any existing CSV, merges in ICS entries that are not already present,
    sorts the result, saves it, and returns (csv_path, merged_entries).

    Called whenever an ICS file is loaded in interactive mode so that data
    is persisted across restarts.
    """
    csv_path = os.path.splitext(ics_path)[0] + ".csv"

    existing: List[SpecialDayEntry] = []
    if os.path.exists(csv_path):
        try:
            existing = _load_csv_entries(csv_path)
        except (OSError, IOError, csv.Error):
            existing = []

    diff = compare_entries(ics_entries, existing)
    new_entries: List[SpecialDayEntry] = diff["new"]

    merged = sorted(existing + new_entries, key=lambda e: (e.start, e.end, e.type, e.name))
    save_csv_entries(csv_path, merged)

    return csv_path, merged


def expand_entries(entries: List[SpecialDayEntry]) -> Dict[date, Tuple[str, str]]:
    """
    Expand a list of SpecialDayEntry objects into a flat date → (type, name) dict.
    When ranges overlap, the last entry wins.
    """
    result: Dict[date, Tuple[str, str]] = {}
    for entry in entries:
        current = entry.start
        while current <= entry.end:
            result[current] = (entry.type, entry.name)
            current += timedelta(days=1)
    return result


def compare_entries(
    ics_entries: List[SpecialDayEntry],
    csv_entries: List[SpecialDayEntry],
) -> Dict[str, List]:
    """
    Diff ICS entries against CSV entries using (start, end) as the match key.
    Returns a dict with:
      'new'       — in ICS, not in CSV
      'conflicts' — same (start, end), but different name or type  → list of (ics, csv) tuples
      'existing'  — identical in both
      'csv_only'  — in CSV, not in ICS (manual entries)
    """
    csv_map = {(e.start, e.end): e for e in csv_entries}
    ics_map = {(e.start, e.end): e for e in ics_entries}

    new_entries: List[SpecialDayEntry]                        = []
    conflicts:   List[Tuple[SpecialDayEntry, SpecialDayEntry]] = []
    existing:    List[SpecialDayEntry]                        = []

    for key, ics_e in ics_map.items():
        if key not in csv_map:
            new_entries.append(ics_e)
        else:
            csv_e = csv_map[key]
            if ics_e.name != csv_e.name or ics_e.type != csv_e.type:
                conflicts.append((ics_e, csv_e))
            else:
                existing.append(csv_e)

    csv_only = [e for key, e in csv_map.items() if key not in ics_map]

    return {
        "new":       new_entries,
        "conflicts": conflicts,
        "existing":  existing,
        "csv_only":  csv_only,
    }
