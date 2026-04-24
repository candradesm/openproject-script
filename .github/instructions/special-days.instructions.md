# Special Days Instructions

## Overview

Special days (festives and vacations) are loaded from CSV or ICS files and used to skip or override the activity for specific dates during time entry logging. The `SpecialDayEntry` dataclass is the core model. The built-in file manager supports create, edit, remove, and ICS import workflows.

## Data Model

```python
@dataclass
class SpecialDayEntry:
    start: date       # inclusive start date
    end:   date       # inclusive end date
    type:  str        # 'festive' | 'vacation'
    name:  str        # human-readable label
```

- `end` must be >= `start`; single-day entries have `start == end`
- `type` is always lowercase: `"festive"` or `"vacation"`

## CSV Format

```csv
start_date,end_date,type,name
2026-01-01,2026-01-01,festive,New Year's Day
2026-08-03,2026-08-14,vacation,Summer Vacation
```

- Header row is mandatory: `start_date,end_date,type,name`
- Dates: ISO 8601 (`YYYY-MM-DD`)
- Type: `festive` or `vacation` (any other value is coerced to `festive`)
- CSV is read/write; ICS is read-only

## ICS Support

ICS files are parsed with regex (no external library). Type detection uses `CATEGORIES`:

| CATEGORIES value | Detected type |
|-----------------|---------------|
| `VACATION` | `vacation` |
| `TIME OFF` | `vacation` |
| `LEAVE` | `vacation` |
| anything else | `festive` |

ICS multi-day events: `DTEND` is exclusive in ICS all-day events, so the parser subtracts one day:
```python
dtend = dtend - timedelta(days=1)
```

## File Loading

```python
load_special_day_entries(path: str) -> List[SpecialDayEntry]
```

- Auto-detects format by extension (`.csv` → CSV, `.ics` → ICS)
- Unknown extension: tries CSV first, then ICS
- Returns empty list on parse failure (never raises)

## Expanding to a Date Map

```python
special_days = expand_entries(entries)  # Dict[date, Tuple[str, str]]
# e.g. {date(2026,1,1): ("festive", "New Year's Day")}
```

- Overlapping ranges: last entry wins
- Used by `run()` to check each date before logging

## Behavior in `run()`

For each candidate date:
1. Check `special_days` dict — if found, apply strategy:
   - If `festive_activity_id` / `vacation_activity_id` is set → log with override activity
   - If override is `None` → skip the date entirely
2. Then check weekend → skip if Saturday/Sunday
3. Then check existing entries → skip if already logged

## ICS Import Diff Logic

`compare_entries(ics_entries, csv_entries)` returns:

| Key | Meaning |
|-----|---------|
| `new` | In ICS, not in CSV — candidates to import |
| `conflicts` | Same `(start, end)` key, different `name` or `type` |
| `existing` | Identical in both — no action needed |
| `csv_only` | In CSV, not in ICS — manual entries, untouched |

Match key is `(start, end)` tuple — not the name.

## File Manager Menu

The `_manage_special_days()` function provides a full TUI manager:
1. View all entries (grouped by type)
2. Add entry (interactive prompts)
3. Edit entry (pick by number)
4. Remove entry (pick by number)
5. Import from ICS (diff + selective import)
6. Save As... (copy to new path)
7. Close (return to session)

Auto-saves to CSV on every modification (add/edit/remove/import).

## Best Practices
1. Always use `expand_entries()` before passing to `run()` — never pass raw `List[SpecialDayEntry]`
2. Sort entries by `(start, end)` when saving — `save_csv_entries()` does this automatically
3. Validate `end >= start` before creating a `SpecialDayEntry`
4. Use `_fmt_range(entry)` for human-readable display of date ranges
5. ICS files are read-only — always save to CSV for persistence

## Common Pitfalls
1. **Forgetting ICS DTEND is exclusive** → off-by-one day in multi-day events
2. **Passing raw entries to `run()` instead of expanded dict** → dates won't match
3. **Assuming type is always valid** → coerce unknown types to `"festive"` defensively
4. **Not handling `OSError` when loading files** → crash if file is missing or unreadable
