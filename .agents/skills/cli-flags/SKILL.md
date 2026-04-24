---
name: cli-flags
description: IMPORTANT: Load when adding new CLI flags, changing argument validation, or modifying mode detection. Wrong required/optional setup = broken interactive mode or silent CI failures.
---

## When to use me
- Adding new `--flags` to `build_arg_parser()`
- Changing validation in `validate_flag_args()`
- Modifying mode detection logic in `main()`
- Adding env var support for new flags

## Not intended for
- API changes → use `api-client` skill
- Special days logic → use `special-days` skill

---

## Key Rules (MUST)

- Mode detection: `if args.work_package_id is None → interactive_mode()`
- Never use `required=True` in `add_argument` for flags that are only required in flag mode
- All cross-flag validation goes in `validate_flag_args()`, not `main()`
- Connection flags must support env var fallback via `os.environ.get()`
- New features must work in BOTH interactive and flag-based modes

## Blockers (MUST NOT)
- Using `required=True` in `argparse` for flag-mode-only flags → breaks interactive mode
- Putting cross-flag validation in `main()` → inconsistent error messages
- Adding flags without env var support for connection-related options

## Argument Group Structure

```python
conn    = parser.add_argument_group("Connection")
entry   = parser.add_argument_group("Time entry details")
dates   = parser.add_argument_group("Date selection (choose one mode)")
special = parser.add_argument_group("Special days")
# Other flags added directly to parser
```

## Adding a New Flag (Checklist)

- [ ] Add to correct argument group in `build_arg_parser()`
- [ ] Add validation in `validate_flag_args()` if cross-flag rules apply
- [ ] Wire into `main()` for flag-based mode
- [ ] Wire into `interactive_mode()` / `_collect_one_entry()` for interactive mode
- [ ] Add env var support if it's a connection/config option
- [ ] Update `README.md` argument table

## Env Var Pattern

```python
conn.add_argument(
    "--my-option",
    default=os.environ.get("MY_OPTION_ENV_VAR"),
    help="Description (or set MY_OPTION_ENV_VAR env var).",
)
```

## Date Flag Validation

```python
if not args.date and not args.start_date:      → error: date mode required
if args.start_date and not args.end_date:      → error: end-date required
if args.end_date and not args.start_date:      → error: start-date required
if args.start_date > args.end_date:            → error: start must be ≤ end
```

## References
- `.github/instructions/cli-flags.instructions.md` — full CLI flags docs
