"""Resolve the app's poll/render loop rate from ``app.target_fps``.

SPEC-ui-setup-task-selection.md S25: ``target_fps`` is either an explicit
number (always wins) or ``"auto"`` (also the meaning of a missing key), which
follows the connected tracker's own sample rate so a 60 Hz (USB2) device is
not polled at 150 Hz for mostly stale samples.
"""

from __future__ import annotations

import math
from typing import Any

FALLBACK_FPS = 60

_MISSING = object()


def _parse_positive_fps(value: Any) -> int | None:
    """``int(value)`` when it is a finite number (or numeric string) >= 1, else None."""
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or int(number) < 1:
        return None
    return int(number)


def _is_auto(value: Any) -> bool:
    # None covers an empty YAML value (``target_fps:``), same as a missing key.
    return value is _MISSING or value is None or (
        isinstance(value, str) and value.strip().lower() == "auto"
    )


def target_fps_is_invalid(config_value: Any) -> bool:
    """True when ``config_value`` is neither ``auto``/missing nor a positive number."""
    return not _is_auto(config_value) and _parse_positive_fps(config_value) is None


def resolve_target_fps(
    config_value: Any, device_rate_hz: float | None, is_live: bool
) -> tuple[int, str]:
    """Return ``(fps, source)`` with source ``"config"``, ``"device"`` or ``"fallback"``.

    Never raises. A bad ``config_value`` falls back to 60; callers that want
    to warn about it check :func:`target_fps_is_invalid`.
    """
    explicit = None if _is_auto(config_value) else _parse_positive_fps(config_value)
    if explicit is not None:
        return explicit, "config"
    if _is_auto(config_value) and is_live:
        rate = _parse_positive_fps(device_rate_hz)
        if rate is not None:
            return rate, "device"
    return FALLBACK_FPS, "fallback"


def config_target_fps(config: dict[str, Any]) -> Any:
    """``app.target_fps`` from a config dict, or a missing marker (= ``auto``)."""
    return (config.get("app") or {}).get("target_fps", _MISSING)
