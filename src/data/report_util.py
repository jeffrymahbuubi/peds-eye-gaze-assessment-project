"""Small parsing and rounding helpers shared by the report modules
(SPEC-compass-task-flow.md 4D). A value that cannot be read is ``None``, never 0."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def to_int(raw: Any) -> int | None:
    """``int`` of a CSV/JSON value, ``None`` for blank or unreadable."""
    try:
        return int(float(raw)) if raw not in (None, "") else None
    except (TypeError, ValueError):
        return None


def to_float(raw: Any) -> float | None:
    """``float`` of a CSV/JSON value, ``None`` for blank or unreadable."""
    try:
        return float(raw) if raw not in (None, "") else None
    except (TypeError, ValueError):
        return None


def round_or_none(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


def mean_or_none(values: Sequence[float | None], digits: int) -> float | None:
    """Mean of the values that are present, rounded; ``None`` when none is."""
    present = [v for v in values if v is not None]
    return round(sum(present) / len(present), digits) if present else None
