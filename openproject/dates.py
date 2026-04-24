"""Date utilities."""
import argparse
from datetime import date, timedelta
from typing import List


def parse_date_arg(value: str) -> date:
    """argparse type converter for YYYY-MM-DD dates."""
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid date format '{value}'. Expected YYYY-MM-DD (e.g. 2026-03-12)."
        )


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5


def date_range(start: date, end: date) -> List[date]:
    result, current = [], start
    while current <= end:
        result.append(current)
        current += timedelta(days=1)
    return result


def hours_to_iso8601(hours: float) -> str:
    total_minutes = int(hours * 60)
    h, m = divmod(total_minutes, 60)
    return f"PT{h}H{m}M" if m else f"PT{h}H"


def _parse_iso_duration(duration: str) -> float:
    s = duration.upper()
    if s.startswith("PT"):
        s = s[2:]
    hours, minutes = 0.0, 0.0
    if "H" in s:
        h_parts = s.split("H", 1)
        hours = float(h_parts[0])
        s = h_parts[1]
    if "M" in s:
        minutes = float(s.split("M", 1)[0])
    return hours + minutes / 60.0
