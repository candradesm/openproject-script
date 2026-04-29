"""Interactive prompt helpers."""
import getpass
import sys
from datetime import date
from typing import List, Optional

from openproject.theme import _t, _c, RED, CYAN, BOLD, DIM


def prompt(question: str, default: str = "", required: bool = True) -> str:
    """Prompt with optional default; repeat until non-empty when required."""
    hint = f" [{_c(DIM, default)}]" if default else ""
    while True:
        try:
            value = input(f"  {question}{hint}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)
        if value:
            return value
        if default:
            return default
        if not required:
            return ""
        print(f"  {_t('🙊', _c(RED, '✘'))}  {_t('This field is required, monke!', 'This field is required.')}")


def prompt_secret(question: str) -> str:
    """Prompt for a sensitive value (input not echoed)."""
    while True:
        try:
            value = getpass.getpass(f"  {question}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)
        if value:
            return value
        print(f"  {_t('🙊', _c(RED, '✘'))}  {_t('This field is required, monke!', 'This field is required.')}")


def prompt_int(question: str, default: Optional[int] = None, min_val: int = 1) -> int:
    """Prompt for a positive integer with optional default."""
    default_str = str(default) if default is not None else ""
    while True:
        raw = prompt(question, default=default_str, required=(default is None))
        try:
            value = int(raw)
            if value < min_val:
                raise ValueError()
            return value
        except ValueError:
            print(f"  {_t('🙊', _c(RED, '✘'))}  {_t(f'Enter a whole number ≥ {min_val}, monke!', f'Enter a whole number ≥ {min_val}.')}")


def prompt_float(question: str, default: float = 8.0) -> float:
    """Prompt for a positive float with a default."""
    while True:
        raw = prompt(question, default=str(default))
        try:
            value = float(raw)
            if value <= 0:
                raise ValueError()
            return value
        except ValueError:
            _pos_err = _t(
                "That's not a positive number, monke! Try something like 8 or 7.5.",
                "Enter a positive number (e.g. 8 or 7.5).",
            )
            print(f"  {_t('🙊', _c(RED, '✘'))}  {_pos_err}")


def prompt_date(question: str, default: Optional[date] = None) -> date:
    """Prompt for a YYYY-MM-DD date with optional default."""
    default_str = default.isoformat() if default else ""
    while True:
        raw = prompt(question, default=default_str, required=(default is None))
        try:
            return date.fromisoformat(raw)
        except ValueError:
            _date_err = _t(
                f"Invalid date '{raw}', monke! Use YYYY-MM-DD (e.g. 2026-03-12).",
                f"Invalid date '{raw}'. Use YYYY-MM-DD.",
            )
            print(f"  {_t('🙊', _c(RED, '✘'))}  {_date_err}")


def prompt_choice(question: str, choices: List[str], default: int = 1) -> int:
    """Show a numbered menu; return the 1-based index of the chosen option."""
    print(f"\n  {question}")
    for i, label in enumerate(choices, start=1):
        marker = _c(CYAN, "▸") if i == default else " "
        print(f"    {marker} {_c(BOLD, str(i))}) {label}")
    print()
    while True:
        raw = prompt("Choice", default=str(default))
        # Allow "exit" to propagate upward
        if raw.lower() in ("exit", "quit", "q"):
            raise SystemExit(0)
        try:
            idx = int(raw)
            if 1 <= idx <= len(choices):
                return idx
        except ValueError:
            pass
        _choice_err = _t(
            f"Pick a number between 1 and {len(choices)}, monke!",
            f"Enter a number between 1 and {len(choices)}.",
        )
        print(f"  {_t('🙊', _c(RED, '✘'))}  {_choice_err}")


def prompt_bool(question: str, default: bool = False) -> bool:
    """Prompt for a yes/no answer."""
    hint = "Y/n" if default else "y/N"
    raw = prompt(question, default=hint, required=False)
    if not raw or raw.lower() == hint.lower():
        return default
    return raw.lower() in ("y", "yes", "1", "true")


def _is_exit(value: str) -> bool:
    return value.strip().lower() in ("exit", "quit", "q", "bye")
