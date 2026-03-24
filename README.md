# OpenProject Time Entry Logger

## Summary

**TL;DR**
- Logs time entries in OpenProject via the API v3 — no browser needed.
- Two modes: **interactive** (guided prompts, session loop) and **flag-based** (scriptable, CI-friendly).
- Fetches projects, work packages and activities from the API — no IDs to memorise.
- Automatically skips weekends and dates that already have an entry.
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
