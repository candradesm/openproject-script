# OpenProject Time Entry Logger

## Summary

**TL;DR**

- Logs time entries in OpenProject via the API v3 — no browser needed.
- Two modes: **interactive** (guided prompts, session loop) and **flag-based** (scriptable, CI-friendly).
- Fetches projects, work packages and activities from the API — no IDs to memorise.
- Automatically skips weekends and dates that already have an entry.
- Skips (or re-routes) festives and vacations loaded from a CSV or ICS file.
- Built-in special days file manager — create, edit, and import from ICS calendars.
- Dry-run mode lets you preview what would be logged before committing.
- Zero external dependencies — pure Python 3 stdlib.

---

## Modes

### Interactive mode

Run the script with no required arguments. It will guide you through every step with menus and prompts, and let you log multiple entries in a single session without re-entering credentials.

```bash
python3 openproject_time_entry.py
```

Optional flags that also work in interactive mode:

```bash
python3 openproject_time_entry.py --monke      # enable fun theme
python3 openproject_time_entry.py --insecure   # skip SSL verification
python3 openproject_time_entry.py --monke --insecure
```

### Flag-based mode

Pass all values as CLI flags. Useful for scripting or CI pipelines.

```bash
python3 openproject_time_entry.py \
  --base-url https://openproject.example.com \
  --api-key YOUR_API_KEY \
  --work-package-id 1296 \
  --date 2026-03-12
```

---

## Special Days

Special days are **festives** (public holidays) and **vacation** days that you want to handle differently from regular working days. When logging a date range, the tool detects any special days in that range and either skips them or logs them under a different activity ID.

### File formats

Two formats are supported:

| Format | Extension | Read | Write | Notes |
|--------|-----------|------|-------|-------|
| CSV | `.csv` | ✔ | ✔ | Editable local copy. Columns: `start_date,end_date,type,name` |
| ICS | `.ics` | ✔ | ✗ | Export from Google Calendar, Outlook, etc. Read-only import source. |

**Runtime read priority:** CSV is preferred. If no CSV is present, the tool falls back to the ICS file directly.

### How it works

- In **flag-based mode**, pass `--special-days-file` with the path to your CSV or ICS file.
  - If `--festive-activity-id` is provided, festive days are logged under that activity instead of being skipped.
  - If `--vacation-activity-id` is provided, vacation days are logged under that activity instead of being skipped.
  - If either flag is omitted, that day type is simply **skipped** — safe for CI pipelines.
- In **interactive mode**, the special days file manager is accessible from the *"What next?"* menu at the end of each session.

### File manager (interactive mode)

The built-in manager lets you maintain your CSV file without leaving the tool:

| Action | Description |
|--------|-------------|
| View all entries | Lists festives and vacations grouped by type. |
| Add entry | Guided prompt to add a new festive or vacation range. |
| Edit entry | Pick an existing entry and update any field. |
| Remove entry | Pick and delete an entry with confirmation. |
| Import from ICS | Parses an ICS file, shows new/conflicting/existing entries, and lets you selectively import. Auto-saves on change. |
| Save As… | Write the current entries to a different file path. |

---

## Arguments

### Connection

| Flag | Environment variable | Description | Required |
|---|---|---|---|
| `--base-url` | `OPENPROJECT_BASE_URL` | Base URL of the OpenProject instance. | Yes |
| `--api-key` | `OPENPROJECT_API_KEY` | API access token. Get it from: *My Account → Access tokens → API*. | Yes |
| `--insecure` | `OPENPROJECT_INSECURE=1` | Skip SSL certificate verification. Use this for instances with a self-signed certificate. | No |

### Time entry details

| Flag | Environment variable | Description | Default |
|---|---|---|---|
| `--work-package-id` | — | ID of the work package to log time against. **Required in flag mode.** | — |
| `--user-id` | — | User ID to log time for. Auto-detected from the API key if omitted. | Auto |
| `--activity-id` | — | Activity ID to associate with the entry. | `3` |
| `--hours` | — | Hours to log per day. | `8.0` |
| `--comment` | — | Comment to attach to each time entry. | *(none)* |

### Date selection

Exactly one of the following modes is required in flag mode. Interactive mode prompts for this.

| Flag | Description |
|---|---|
| `--date YYYY-MM-DD` | Log a single date. |
| `--start-date YYYY-MM-DD` + `--end-date YYYY-MM-DD` | Log a date range (weekends are skipped automatically). |

### Special days

| Flag | Description | Default |
|---|---|---|
| `--special-days-file PATH` | Path to a CSV or ICS file containing festives/vacation days to skip or reroute. | *(none)* |
| `--festive-activity-id ID` | Activity ID to use when logging a festive day instead of skipping it. If omitted, festive days are skipped. | *(skip)* |
| `--vacation-activity-id ID` | Activity ID to use when logging a vacation day instead of skipping it. If omitted, vacation days are skipped. | *(skip)* |

### Other

| Flag | Environment variable | Description | Default |
|---|---|---|---|
| `--dry-run` | — | Preview what would be logged without creating any entries. After the preview, the script offers to execute for real. | `false` |
| `--monke` | `MONKE_THEME=1` | Enable the monkey-themed output (bananas, emojis, jungle vocabulary). Plain output is the default. | `false` |

---

## Environment variables

All connection options can be pre-set as environment variables to avoid typing them on every run:

```bash
export OPENPROJECT_BASE_URL=https://openproject.example.com
export OPENPROJECT_API_KEY=your_token_here
export OPENPROJECT_INSECURE=1   # optional, for self-signed certs
export MONKE_THEME=1            # optional, enable fun theme
```

In interactive mode, these values are used as defaults in the prompts. In flag-based mode, they are read directly — no flag needed.

---

## Summary output

After logging, the tool prints a summary of what happened:

```
Summary:
  ✔  Logged           : 18
  ⏭  Skipped (weekend)  : 8
  ⏭  Skipped (existing) : 0
  ⏭  Skipped (festive)  : 2
  ⏭  Skipped (vacation) : 5
  ✘  Failed             : 0
```

`Skipped (festive)` and `Skipped (vacation)` lines only appear when at least one day of that type was skipped.

---

## Examples

**Interactive session (plain)**

```bash
python3 openproject_time_entry.py
```

**Interactive session (monke theme + self-signed cert)**

```bash
python3 openproject_time_entry.py --monke --insecure
```

**Single date, flag-based**

```bash
python3 openproject_time_entry.py \
  --base-url https://openproject.example.com \
  --api-key YOUR_API_KEY \
  --work-package-id 1296 \
  --date 2026-03-12
```

**Date range, flag-based**

```bash
python3 openproject_time_entry.py \
  --base-url https://openproject.example.com \
  --api-key YOUR_API_KEY \
  --work-package-id 1296 \
  --start-date 2026-03-01 \
  --end-date 2026-03-31 \
  --hours 8 \
  --activity-id 3 \
  --comment "Development work"
```

**Date range with special days file (skip festives, reroute vacations)**

```bash
python3 openproject_time_entry.py \
  --base-url https://openproject.example.com \
  --api-key YOUR_API_KEY \
  --work-package-id 1296 \
  --start-date 2026-01-01 \
  --end-date 2026-01-31 \
  --special-days-file ~/calendars/festives.csv \
  --vacation-activity-id 7
# Festive days are skipped; vacation days are logged under activity 7
```

**Dry-run preview, then execute for real**

```bash
python3 openproject_time_entry.py \
  --base-url https://openproject.example.com \
  --api-key YOUR_API_KEY \
  --work-package-id 1296 \
  --start-date 2026-03-01 \
  --end-date 2026-03-31 \
  --dry-run
# After the preview, the script will ask: "Looks good — execute for real?"
```

**Using environment variables (no flags needed for connection)**

```bash
export OPENPROJECT_BASE_URL=https://openproject.example.com
export OPENPROJECT_API_KEY=your_token_here

python3 openproject_time_entry.py \
  --work-package-id 1296 \
  --date 2026-03-12
```

---

## Project structure

```
openproject_time_entry.py     # Entry point — delegates to openproject.cli.main
openproject/
  __init__.py
  theme.py                    # Output helpers, _t(), _c(), ANSI colors, log_* functions
  prompts.py                  # Interactive prompt helpers
  dates.py                    # Date parsing, weekend check, ISO 8601 duration helpers
  special_days/
    __init__.py
    model.py                  # SpecialDayEntry dataclass
    io.py                     # CSV/ICS load, save, expand, compare
    ui.py                     # Special days file manager (interactive)
  client.py                   # OpenProjectClient — all HTTP/API calls
  runner.py                   # run(), print_summary() — core logging loop
  interactive.py              # Interactive session loop
  cli.py                      # Argument parser, flag validation, main()
tests/
  test_dates.py               # 20 tests
  test_special_days_io.py     # 26 tests
  test_runner.py              # 29 tests
  test_cli.py                 # 16 tests
```
