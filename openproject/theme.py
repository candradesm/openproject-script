"""Theme toggle, ANSI colors, and logging helpers."""
import os
import sys
from typing import Optional

# ── Theme toggle ───────────────────────────────────────────────────────────────
_MONKE: bool = os.environ.get("MONKE_THEME", "0").strip() == "1"


def set_monke(value: bool) -> None:
    global _MONKE
    _MONKE = value


def _t(fun: str, plain: str) -> str:
    """Return the fun (monkey-themed) string or the plain string based on _MONKE."""
    return fun if _MONKE else plain


# ── Terminal colors ────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"


def _c(color: str, text: str) -> str:
    return f"{color}{text}{RESET}"


def log_info(msg: str) -> None:
    print(f"  {_t('🐵', _c(BLUE, 'ℹ'))}  {msg}")


def log_ok(msg: str) -> None:
    print(f"  {_t('🍌', _c(GREEN, '✔'))}  {msg}")


def log_skip(msg: str) -> None:
    print(f"  {_t('🙈', _c(YELLOW, '⏭'))}  {msg}")


def log_error(msg: str) -> None:
    print(f"  {_t('🙊', _c(RED, '✘'))}  {_c(RED, msg)}", file=sys.stderr)


def log_dry(msg: str) -> None:
    print(f"  {_t('🐒', _c(CYAN, '~'))}  {_c(CYAN, '[DRY-RUN]')} {msg}")


def log_section(msg: str) -> None:
    print(f"\n{_c(BOLD, msg)}")


def log_rule(label: str = "") -> None:
    line = f"── {label} " if label else "──"
    print(f"\n  {_c(DIM, line + '─' * max(0, 48 - len(line)))}")


def log_divider() -> None:
    print(f"  {_c(DIM, '─' * 52)}")
