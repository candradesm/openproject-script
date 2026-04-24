# Code Style Instructions

## Overview

This is a single-file Python 3.8+ script with zero external dependencies. Code style prioritises readability, consistency, and the dual-mode output pattern. No linter config files exist — `py_compile` is the only build check.

## Python Version Constraint

- **Target**: Python 3.8+
- **Forbidden**: f-strings with `=` (3.8+), `dict | dict` merge (3.9+), `match` statements (3.10+), `X | Y` type hints (3.10+)
- **Use**: `Optional[X]`, `List[X]`, `Dict[K, V]`, `Tuple[X, Y]` from `typing`

```python
# CORRECT (3.8 compatible)
from typing import Dict, List, Optional, Tuple
def foo(x: Optional[int] = None) -> List[str]: ...

# WRONG (3.10+ only)
def foo(x: int | None = None) -> list[str]: ...
```

## Dual-Mode Output (MANDATORY)

Every user-facing string must use `_t(fun, plain)`:

```python
# CORRECT
log_ok(_t("🍌 Bananza logged!", "Entry created."))
log_error(_t("🙊 Something went wrong, monke!", "An error occurred."))
log_skip(_t("🙈 Already logged, skipping.", "Date already has an entry, skipping."))

# WRONG — hardcoded string
log_ok("Entry created.")
```

The `_MONKE` global is set once at startup from `--monke` flag or `MONKE_THEME=1` env var.

## Logging Helpers

Always use the `log_*` helpers — never `print()` directly for user-facing output:

| Helper | Icon (monke) | Icon (plain) | Use for |
|--------|-------------|--------------|---------|
| `log_info(msg)` | 🐵 | ℹ (blue) | Informational messages |
| `log_ok(msg)` | 🍌 | ✔ (green) | Success messages |
| `log_skip(msg)` | 🙈 | ⏭ (yellow) | Skipped dates/items |
| `log_error(msg)` | 🙊 | ✘ (red) | Errors (also prints to stderr) |
| `log_dry(msg)` | 🐒 | ~ (cyan) | Dry-run previews |
| `log_section(msg)` | — | — | Section headers (bold) |
| `log_rule(label)` | — | — | Visual dividers with optional label |
| `log_divider()` | — | — | Plain horizontal divider |

## Color Usage

```python
# Use _c(COLOR, text) — never raw ANSI codes inline
log_info(f"User: {_c(BOLD, user_name)}  {_c(DIM, f'(ID: {user_id})')}")

# Available colors
GREEN, YELLOW, RED, BLUE, CYAN, BOLD, DIM, RESET
```

## Function Naming Conventions

| Prefix | Meaning |
|--------|---------|
| `prompt_*` | Interactive input helpers |
| `log_*` | Output/display helpers |
| `_load_*` | File loading (private) |
| `_save_*` / `save_*` | File saving |
| `_manage_*` | Interactive TUI managers (private) |
| `_collect_*` | Interactive data collection (private) |
| `_pick_*` | Interactive selection from a list (private) |
| `_fmt_*` | Formatting helpers (private) |
| `_is_*` | Boolean predicates (private) |
| `_href_*` | HAL link helpers (private) |
| `_connect_*` | Connection helpers (private) |

## Single-File Constraint

- **All code stays in `openproject_time_entry.py`**
- Do not create modules, packages, or helper files
- Do not use `from __future__ import annotations`
- Keep section comments (`# ── Section name ──`) to maintain navigability

## Imports

Only stdlib imports are allowed. Keep them sorted alphabetically:

```python
import argparse
import base64
import csv
import getpass
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
```

## Type Hints

Use type hints on all public functions and methods:

```python
def run(
    client: OpenProjectClient,
    work_package_id: int,
    ...
    special_days: Optional[Dict[date, Tuple[str, str]]] = None,
) -> dict:
```

## Best Practices
1. Use `_t(fun, plain)` for every user-facing string — no exceptions
2. Use `log_*` helpers instead of `print()` for all output
3. Catch `RuntimeError` from `OpenProjectClient` — never let HTTP errors propagate raw
4. Use `Optional[X]` not `X | None` for Python 3.8 compatibility
5. Keep section headers (`# ── Section ──`) to maintain script navigability

## Common Pitfalls
1. **Using `print()` directly** instead of `log_*` helpers → breaks theme consistency
2. **Hardcoding strings** without `_t()` → breaks monke theme
3. **Using 3.9+ type syntax** (`list[str]`, `dict[str, int]`) → `TypeError` on Python 3.8
4. **Adding external imports** → breaks zero-dependency constraint
5. **Splitting into multiple files** → breaks the single-file design
