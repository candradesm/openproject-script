---
name: special-days
description: IMPORTANT: Load when touching SpecialDayEntry, CSV/ICS loading, the file manager, or the special days logic in run(). Wrong date expansion or ICS off-by-one = days logged on holidays.
---

## When to use me
- Modifying `SpecialDayEntry`, `load_special_day_entries`, `expand_entries`
- Changing ICS parsing (`_load_ics_entries`, `_ics_extract_*`)
- Modifying the file manager (`_manage_special_days`, `_add_entry_interactive`, etc.)
- Changing how `run()` handles special days

## Not intended for
- API client changes → use `api-client` skill
- CLI flags → use `cli-flags` skill

---

## Key Rules (MUST)

- `SpecialDayEntry.type` is always lowercase: `"festive"` or `"vacation"`
- `end >= start` always — validate before creating entries
- ICS `DTEND` is **exclusive** for all-day events → subtract 1 day: `dtend = dtend - timedelta(days=1)`
- Always call `expand_entries()` before passing to `run()` — never pass raw `List[SpecialDayEntry]`
- CSV is read/write; ICS is read-only

## Blockers (MUST NOT)
- Passing `List[SpecialDayEntry]` directly to `run()` — must be `Dict[date, Tuple[str, str]]`
- Creating `SpecialDayEntry` with `end < start`
- Treating ICS `DTEND` as inclusive → off-by-one on multi-day events

## Data Flow

```
File (CSV/ICS)
  → load_special_day_entries(path)     # List[SpecialDayEntry]
  → expand_entries(entries)            # Dict[date, Tuple[str, str]]
  → run(..., special_days=sd)          # checked per date
```

## Type Detection from ICS CATEGORIES

| CATEGORIES contains | Detected type |
|--------------------|---------------|
| `vacation` | `vacation` |
| `time off` | `vacation` |
| `leave` | `vacation` |
| anything else | `festive` |

## Behavior in run() per Date

1. Date in `special_days`?
   - `festive_activity_id` set → log with that activity
   - `vacation_activity_id` set → log with that activity
   - Override is `None` → skip date
2. Weekend? → skip
3. Already has entries? → skip
4. Otherwise → create entry

## CSV Format

```csv
start_date,end_date,type,name
2026-01-01,2026-01-01,festive,New Year's Day
2026-08-03,2026-08-14,vacation,Summer Vacation
```

## References
- `.github/instructions/special-days.instructions.md` — full special days docs
