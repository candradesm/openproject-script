# OpenProject Time Entry Logger - Copilot Instructions

## Project Overview

**OpenProject Time Entry Logger** is a zero-dependency Python 3 CLI tool that logs time entries to an OpenProject instance via the REST API v3. It runs in two modes: **interactive** (guided prompts, session loop) and **flag-based** (scriptable, CI-friendly).

### Key Information
- **Language**: Python 3 (stdlib only — no external dependencies)
- **Build Tool**: None (Python package, no build step)
- **Architecture**: Python package (`openproject/`) with a thin entry-point script
- **Key Framework**: `argparse`, `urllib`, `csv`, `ssl` (all stdlib)
- **Entry Point**: `openproject_time_entry.py` (delegates to `openproject.cli.main`)

### Main Features
- Interactive session loop — log multiple entries without re-entering credentials
- Flag-based mode for scripting and CI pipelines
- Fetches projects, work packages, and activities from the API (no IDs to memorise)
- Auto-detects user ID from the API key
- Skips weekends and dates that already have entries
- Special days support: load CSV or ICS files with festives and vacations
- Built-in special days file manager (create, edit, import from ICS)
- Dry-run mode to preview without creating anything
- Monkey-themed output (`--monke` flag or `MONKE_THEME=1`)

## Technical Summary

### Architecture Patterns
- **Python package** — logic split across `openproject/` sub-modules; thin entry point delegates to `openproject.cli.main`
- **Layered modules** — `theme` → `prompts` / `dates` → `special_days` → `client` → `runner` → `interactive` → `cli`
- **Theme toggle** — `_MONKE` bool in `openproject/theme.py`; use `theme.set_monke(True)` to enable at runtime; `_t(fun, plain)` helper for dual-mode output
- **Terminal colors** — ANSI escape codes via `_c(color, text)` helper in `theme.py`
- **No classes except `OpenProjectClient`** — everything else is functions

### Project Structure
```
openproject_time_entry.py          # Thin entry point — delegates to openproject.cli.main
openproject/
  __init__.py                      # Minimal package marker
  theme.py                         # _MONKE, set_monke, _t, _c, colors, log_* functions
  prompts.py                       # All prompt_* functions + _is_exit
  dates.py                         # parse_date_arg, is_weekend, date_range, hours_to_iso8601, _parse_iso_duration
  special_days/
    __init__.py                    # Re-exports public API
    model.py                       # SpecialDayEntry dataclass
    io.py                          # ICS/CSV loaders, savers, expand_entries, compare_entries
    ui.py                          # Display helpers and interactive manager (_manage_special_days)
  client.py                        # OpenProjectClient class
  runner.py                        # run(), print_summary()
  interactive.py                   # _pick_from_api_list, _connect_and_identify, _collect_one_entry, interactive_mode
  cli.py                           # build_arg_parser, validate_flag_args, main
README.md                          # Usage documentation
.github/
  copilot-instructions.md          # This file
  instructions/                    # Topic-specific guidance
.agents/skills/                    # Workflow-level skills for agents
```

### Module Dependency Order (no circular imports)
```
theme  ←  (no openproject deps)
prompts  ←  theme
dates  ←  (no openproject deps)
special_days/model  ←  (no openproject deps)
special_days/io  ←  model
special_days/ui  ←  model, io, theme, prompts, dates
client  ←  (no openproject deps)
runner  ←  theme, dates, client
interactive  ←  theme, prompts, dates, special_days, client, runner
cli  ←  all of the above
```

### Key Libraries (all stdlib)
- `argparse`: CLI argument parsing
- `urllib.request` / `urllib.error`: HTTP requests to OpenProject API
- `ssl`: SSL context for insecure connections
- `csv`: Reading/writing special days CSV files
- `re`: ICS file parsing
- `getpass`: Hidden password input
- `dataclasses`: `SpecialDayEntry` model

## Working with This Project

### Before Starting
1. Read `.github/instructions/` for topic-specific guidance
2. Verify Python 3.8+ is installed (`python3 --version`)
3. No `pip install` needed — zero external dependencies

### Common Tasks
- **Run (interactive)**: `python3 openproject_time_entry.py`
- **Run (flag-based)**: `python3 openproject_time_entry.py --base-url URL --api-key TOKEN --work-package-id ID --date YYYY-MM-DD`
- **Run with monke theme**: `python3 openproject_time_entry.py --monke`
- **Dry-run**: add `--dry-run` to any flag-based command
- **Lint**: `python3 -m py_compile openproject_time_entry.py` (syntax check)

### Adding New Features
1. Follow the **module dependency order** — never create circular imports
2. Maintain **zero external dependencies** — stdlib only
3. Apply the `_t(fun, plain)` pattern for any new user-facing strings
4. Use `_c(color, text)` for terminal color output
5. Use `log_*` helpers (`log_info`, `log_ok`, `log_skip`, `log_error`, `log_dry`) for output
6. Add new CLI flags in `build_arg_parser()` and validate in `validate_flag_args()`
7. Handle both interactive and flag-based modes for any new functionality

### Critical Constraints
- **Zero external dependencies** — never add `import` for non-stdlib modules
- **Python 3.8+ compatible** — avoid features from 3.9+
- **Package structure** — keep the `openproject/` package layout; do not collapse back to single file
- **Dual-mode output** — every user-facing string must use `_t(fun, plain)`

## Related Documentation
- **API Client**: `.github/instructions/api-client.instructions.md`
- **Special Days**: `.github/instructions/special-days.instructions.md`
- **CLI Flags**: `.github/instructions/cli-flags.instructions.md`
- **Code Style**: `.github/instructions/code-style.instructions.md`
