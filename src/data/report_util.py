"""Small parsing and rounding helpers shared by the report modules
(SPEC-compass-task-flow.md 4D). A value that cannot be read is ``None``, never 0."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

DASH = "—"  # a figure that could not be given, in a numeric or date table cell
NOT_RECORDED = "not recorded"  # what a text cell or a report row says when it has no value


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


def ms_to_seconds(ms: Any) -> float | None:
    """Milliseconds (a stored figure) as seconds (what is shown); ``None`` for anything
    that is not a number. The data files keep milliseconds, the screen and the PDF show
    seconds (SPEC-compass-task-flow.md 7.1, V5)."""
    if isinstance(ms, bool):
        return None
    try:
        return float(ms) / 1000.0
    except (TypeError, ValueError):
        return None


def seconds_text(ms: Any, digits: int = 3, dash: str = DASH) -> str:
    """Milliseconds as compact seconds: ``800`` -> "0.8 s", ``8000`` -> "8 s", ``120`` ->
    "0.12 s"; ``dash`` when ``ms`` is not a number. At most ``digits`` decimals, no
    trailing zeros."""
    seconds = ms_to_seconds(ms)
    return dash if seconds is None else f"{round(seconds, digits):g} s"


def round_or_none(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


def mean_or_none(values: Sequence[float | None], digits: int) -> float | None:
    """Mean of the values that are present, rounded; ``None`` when none is."""
    present = [v for v in values if v is not None]
    return round(sum(present) / len(present), digits) if present else None
