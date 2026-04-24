---
name: quality-check
description: CRITICAL: Load BEFORE opening any PR or submitting changes. Missing this = syntax errors and broken script. Validates Python syntax, imports, unit tests, and basic runtime. Pre-PR only.
---

## When to use me
- At the end of a task before opening a PR
- After any modification to files in `openproject/` or `tests/`
- When verifying the package still runs correctly

## Not intended for
- Day-to-day coding → use project-specific skills
- Code review → use `code-review`

---

## Quality Gates (MUST)

| Gate | Command | Pass condition |
|------|---------|----------------|
| Syntax check | `python3 -m py_compile` on all package files | No output = success |
| Import check | `python3 -c "from openproject.cli import main"` | Must print `imports OK` |
| Unit tests | `python3 -m unittest discover -s tests -v` | All tests pass, 0 failures |
| Help flag | `python3 openproject_time_entry.py --help` | Must print usage, exit 0 |

## Run Sequentially

```
Syntax → Import → Unit tests → Help flag
```

Never skip syntax check or unit tests. A broken test suite = broken tool.

---

## Step 1 — Syntax Check

Compile every `.py` file in the package and tests:

```bash
for f in openproject_time_entry.py \
          openproject/__init__.py \
          openproject/theme.py \
          openproject/prompts.py \
          openproject/dates.py \
          openproject/special_days/__init__.py \
          openproject/special_days/model.py \
          openproject/special_days/io.py \
          openproject/special_days/ui.py \
          openproject/client.py \
          openproject/runner.py \
          openproject/interactive.py \
          openproject/cli.py \
          tests/test_dates.py \
          tests/test_special_days_io.py \
          tests/test_runner.py \
          tests/test_cli.py; do
  python3 -m py_compile "$f" && echo "OK: $f" || echo "FAIL: $f"
done
```

Any `SyntaxError` on any file = **BLOCKER**.

## Step 2 — Import Check

```bash
python3 -c "
from openproject.theme import _t, log_info, log_ok, log_skip, log_error, log_dry, log_section, log_rule, log_divider, set_monke
from openproject.client import OpenProjectClient
from openproject.dates import hours_to_iso8601
from openproject.special_days.io import compare_entries
from openproject.interactive import interactive_mode
from openproject.cli import main, build_arg_parser
print('imports OK')
"
```

Must print `imports OK`. Any `ImportError` or `ModuleNotFoundError` = **BLOCKER** (likely added a non-stdlib import or broke the module graph).

## Step 3 — Unit Tests

```bash
python3 -m unittest discover -s tests -v
```

Expected: **91 tests, 0 failures, 0 errors**.

- Any test failure = **BLOCKER**
- Test count dropping below 91 = **BLOCKER** (tests were deleted)

### Test files and what they cover

| File | Module under test | Tests |
|------|------------------|-------|
| `tests/test_dates.py` | `openproject.dates` | 20 |
| `tests/test_special_days_io.py` | `openproject.special_days.io` + `model` | 26 |
| `tests/test_runner.py` | `openproject.runner` | 29 |
| `tests/test_cli.py` | `openproject.cli` | 16 |

## Step 4 — Help Flag

```bash
python3 openproject_time_entry.py --help
```

Must print the argument help text and exit 0.

---

## Reporting
- **BLOCKER**: SyntaxError, ImportError, test failure, non-zero exit on `--help`
- **WARNING**: Deprecation warnings from stdlib usage, test count below 91
- **PRAISE**: Clean syntax, zero dependencies maintained, all tests green

## References
- `.github/instructions/code-style.instructions.md` — full style rules
