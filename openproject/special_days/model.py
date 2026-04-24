"""SpecialDayEntry data model."""
from dataclasses import dataclass
from datetime import date


@dataclass
class SpecialDayEntry:
    """Represents one festive or vacation entry (possibly spanning multiple days)."""
    start: date
    end: date
    type: str   # 'festive' | 'vacation'
    name: str
