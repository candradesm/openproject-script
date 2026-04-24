# CLI Flags Instructions

## Overview

The script supports two execution modes: **interactive** (no required flags) and **flag-based** (all values passed as CLI arguments). `argparse` handles parsing; `validate_flag_args()` enforces business rules that `argparse` alone cannot express.

## Mode Detection

```python
if args.work_package_id is None:
    interactive_mode(insecure=args.insecure)
    return
```

If `--work-package-id` is absent → interactive mode. Any other flag combination → flag-based mode.

## Flag Reference

### Connection Flags

| Flag | Env Var | Required | Default | Description |
|------|---------|----------|---------|-------------|
| `--base-url` | `OPENPROJECT_BASE_URL` | Yes (flag mode) | — | Instance base URL |
| `--api-key` | `OPENPROJECT_API_KEY` | Yes (flag mode) | — | API access token |
| `--insecure` | `OPENPROJECT_INSECURE=1` | No | `false` | Skip SSL verification |

### Time Entry Flags

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--work-package-id` | Yes (flag mode) | — | Work package ID |
| `--user-id` | No | auto-detect | User ID (auto from API key) |
| `--activity-id` | No | `3` | Activity ID |
| `--hours` | No | `8.0` | Hours per day |
| `--comment` | No | `""` | Comment text |

### Date Flags (mutually exclusive)

| Flag | Description |
|------|-------------|
| `--date YYYY-MM-DD` | Single date |
| `--start-date` + `--end-date` | Date range (inclusive) |

Exactly one mode is required in flag-based mode.

### Special Days Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--special-days-file PATH` | — | CSV or ICS file |
| `--festive-activity-id ID` | `None` (skip) | Activity for festive days |
| `--vacation-activity-id ID` | `None` (skip) | Activity for vacation days |

### Other Flags

| Flag | Env Var | Description |
|------|---------|-------------|
| `--dry-run` | — | Preview without creating entries |
| `--monke` | `MONKE_THEME=1` | Enable monkey-themed output |

## Validation Rules (`validate_flag_args`)

```python
# Required in flag mode
if not args.base_url:      → error
if not args.api_key:       → error
if args.work_package_id is None: → error

# Date mode: exactly one required
if not args.date and not args.start_date: → error
if args.start_date and not args.end_date: → error
if args.end_date and not args.start_date: → error
if args.start_date > args.end_date:       → error

# Value constraints
if args.hours <= 0: → error
```

## Adding New Flags

1. Add to `build_arg_parser()` in the appropriate argument group
2. Add validation logic to `validate_flag_args()` if needed
3. Wire the new flag into `main()` (flag mode) and `interactive_mode()` / `_collect_one_entry()` (interactive mode)
4. Use `_t(fun, plain)` for any new user-facing output strings

```python
# Example: adding a new flag
parser.add_argument(
    "--my-flag",
    type=int,
    default=None,
    metavar="VALUE",
    help="Description of the flag.",
)
```

## Environment Variable Pattern

All connection flags support env vars as fallback:

```python
conn.add_argument("--base-url", default=os.environ.get("OPENPROJECT_BASE_URL"), ...)
conn.add_argument("--api-key",  default=os.environ.get("OPENPROJECT_API_KEY"), ...)
conn.add_argument("--insecure", action="store_true",
                  default=os.environ.get("OPENPROJECT_INSECURE", "0").strip() == "1", ...)
```

In interactive mode, env vars pre-fill prompts as defaults.

## Best Practices
1. Always add new flags to the correct argument group for clean `--help` output
2. Use `type=parse_date_arg` for date flags — never raw `str` with manual parsing
3. Validate cross-flag constraints in `validate_flag_args()`, not in `main()`
4. Support both interactive and flag-based paths for any new feature
5. Document new flags in `README.md` under the appropriate table

## Common Pitfalls
1. **Adding validation in `main()` instead of `validate_flag_args()`** → inconsistent error messages
2. **Forgetting env var support** for connection-related flags → breaks CI pipelines
3. **Using `required=True` in `add_argument`** for flags that are only required in flag mode → breaks interactive mode
4. **Not handling `None` default** for optional int/float flags → `TypeError` when doing arithmetic
