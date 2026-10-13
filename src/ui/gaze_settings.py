"""The gaze-signal and smoothing settings (SPEC-gaze-stability-and-positioning.md 4.1-4.3, 4.8):
the registry entries of the configuration page's "Gaze Smoothing" card, what greys each one,
and the defaults the config file falls back to. Split out of :mod:`settings_registry` to keep it
under the project's 500-line limit; the registry splices :data:`GAZE_LIVE` into ``LIVE_SETTINGS``
at the place the two old smoothing entries sat. No PySide6 import.

The card, in order: Cursor stabilisation, AAC filter length, Smoothing enabled, Smoothing type,
alpha, Steadiness, Responsiveness. Cursor stabilisation is two approaches (4.9): App smoothing
(raw gaze) plus the app's own filter, or Gazepoint Assistive, whose own signal the app never
smooths. Defaults stay ``best`` + ``ema`` (G5), so an old profile or config without the new
keys behaves exactly as before, and a retired ``fixation`` loads as ``best`` (G9).
"""

from __future__ import annotations

from typing import Any

from ..engine.input_choice import POINTER_MOUSE
from ..inputs.gaze_signal import (
    AAC_FILTER_DEFAULT,
    AAC_FILTER_MAX,
    AAC_FILTER_MIN,
    DEFAULT_SMOOTHING_TYPE,
    ONE_EURO_BETA_DEFAULT,
    ONE_EURO_BETA_RANGE,
    ONE_EURO_MIN_CUTOFF_DEFAULT,
    ONE_EURO_MIN_CUTOFF_RANGE,
    POINTER_SIGNALS,
    SIGNAL_ASSISTIVE,
    SIGNAL_BEST,
    SIGNAL_LABELS,
    SMOOTHING_EMA,
    SMOOTHING_LABELS,
    SMOOTHING_ONE_EURO,
    SMOOTHING_TYPES,
    normalize_signal,
)
from .setting_types import LiveSetting

POINTER_SIGNAL_CHOICES: tuple[tuple[str, str], ...] = tuple(
    (value, SIGNAL_LABELS[value]) for value in POINTER_SIGNALS
)
SMOOTHING_TYPE_CHOICES: tuple[tuple[str, str], ...] = tuple(
    (value, SMOOTHING_LABELS[value]) for value in SMOOTHING_TYPES
)

GAZE_LIVE: list[LiveSetting] = [
    LiveSetting(
        "dwell.pointer_signal",
        "Cursor stabilisation",
        "settings",
        "choice",
        tooltip="Who steadies the cursor. App smoothing filters the raw gaze with the settings"
        " below. Gazepoint Assistive uses Gazepoint's own moving-window average, made for eye"
        " typing, and the app adds no smoothing of its own. The recorded gaze is always the"
        " raw gaze.",
        choices=POINTER_SIGNAL_CHOICES,
    ),
    LiveSetting(
        "dwell.aac_filter_samples",
        "AAC filter length (samples)",
        "settings",
        "int",
        AAC_FILTER_MIN,
        AAC_FILTER_MAX,
        1,
        tooltip="Only for Gazepoint Assistive: how many samples Gazepoint averages. Longer ="
        " steadier, slower. This is the same setting as Gazepoint Control's Cursor Smoothing and"
        " is put back to its own value when the tracker disconnects or the app closes.",
    ),
    LiveSetting(
        "dwell.smoothing.enabled",
        "Gaze smoothing enabled",
        "settings",
        "bool",
        tooltip="Smooth out small frame-to-frame jitter in the raw gaze signal.",
    ),
    LiveSetting(
        "dwell.smoothing.type",
        "Smoothing type",
        "settings",
        "choice",
        tooltip="Simple is a running average: steady only by being slow. Adaptive (One Euro) is"
        " steady while the eyes rest and quick when they jump.",
        choices=SMOOTHING_TYPE_CHOICES,
    ),
    LiveSetting(
        "dwell.smoothing.alpha",
        "Smoothing alpha",
        "settings",
        "float",
        0.05,
        1.0,
        0.05,
        tooltip="Lower = steadier cursor, slightly slower to follow a new look."
        " Higher = snappier cursor, more visible jitter.",
    ),
    LiveSetting(
        "dwell.smoothing.min_cutoff_hz",
        "Steadiness (Hz)",
        "settings",
        "float",
        ONE_EURO_MIN_CUTOFF_RANGE[0],
        ONE_EURO_MIN_CUTOFF_RANGE[1],
        0.05,
        tooltip="Adaptive smoothing only. Lower = steadier cursor while the eyes rest,"
        " slightly slower to start moving.",
    ),
    LiveSetting(
        "dwell.smoothing.beta",
        "Responsiveness",
        "settings",
        "float",
        ONE_EURO_BETA_RANGE[0],
        ONE_EURO_BETA_RANGE[1],
        0.1,
        tooltip="Adaptive smoothing only. Higher = the cursor lags less when the eyes jump to"
        " a new place.",
    ),
]

# Greyed in place, never hidden, while the check box it names is off (4.8): the three smoothing
# numbers follow "Gaze smoothing enabled" (the Smoothing type does not, as on the wireframe).
GAZE_DEPENDS_ON = {
    "dwell.smoothing.alpha": "dwell.smoothing.enabled",
    "dwell.smoothing.min_cutoff_hz": "dwell.smoothing.enabled",
    "dwell.smoothing.beta": "dwell.smoothing.enabled",
}

# Greyed while ANY of its ``(choice key, value)`` pairs holds (4.1-4.3, 4.9): the AAC length is for
# Gazepoint Assistive only; every app-smoothing row is for App smoothing only, since the app never
# smooths an Assistive cursor (G10), and within those alpha is for Simple only, Steadiness and
# Responsiveness for Adaptive only. A Mouse pointer has no gaze signal and is never smoothed
# (SPEC-preview-gaze-pointer.md P2, H6), which greys the whole card. A page that lacks a named
# choice never applies that pair. The greyed rows keep their values.
_MOUSE = ("input.pointer", POINTER_MOUSE)
_ASSISTIVE = ("dwell.pointer_signal", SIGNAL_ASSISTIVE)
GAZE_GREYED_BY: dict[str, tuple[tuple[str, str], ...]] = {
    "dwell.pointer_signal": (_MOUSE,),
    "dwell.aac_filter_samples": (_MOUSE, ("dwell.pointer_signal", SIGNAL_BEST)),
    "dwell.smoothing.enabled": (_MOUSE, _ASSISTIVE),
    "dwell.smoothing.type": (_MOUSE, _ASSISTIVE),
    "dwell.smoothing.alpha": (_MOUSE, _ASSISTIVE, ("dwell.smoothing.type", SMOOTHING_ONE_EURO)),
    "dwell.smoothing.min_cutoff_hz": (_MOUSE, _ASSISTIVE, ("dwell.smoothing.type", SMOOTHING_EMA)),
    "dwell.smoothing.beta": (_MOUSE, _ASSISTIVE, ("dwell.smoothing.type", SMOOTHING_EMA)),
}

SMOOTHING_DEFAULTS = {
    "enabled": True,
    "alpha": 0.35,
    "type": DEFAULT_SMOOTHING_TYPE,
    "min_cutoff_hz": ONE_EURO_MIN_CUTOFF_DEFAULT,
    "beta": ONE_EURO_BETA_DEFAULT,
}


def gaze_live_values(dwell_cfg: dict[str, Any]) -> dict[str, Any]:
    """The seven live values of the card, from the merged config's ``dwell`` block, each
    falling back to its default when missing; a choice that is not one of its options (a
    hand-edited file, or the retired ``fixation`` of an old profile) is its default too."""
    smoothing = dwell_cfg.get("smoothing", {})
    kind = smoothing.get("type", SMOOTHING_DEFAULTS["type"])
    return {
        "dwell.pointer_signal": normalize_signal(dwell_cfg.get("pointer_signal")),
        "dwell.aac_filter_samples": dwell_cfg.get("aac_filter_samples", AAC_FILTER_DEFAULT),
        "dwell.smoothing.enabled": smoothing.get("enabled", SMOOTHING_DEFAULTS["enabled"]),
        "dwell.smoothing.type": kind if kind in SMOOTHING_TYPES else DEFAULT_SMOOTHING_TYPE,
        "dwell.smoothing.alpha": smoothing.get("alpha", SMOOTHING_DEFAULTS["alpha"]),
        "dwell.smoothing.min_cutoff_hz": smoothing.get(
            "min_cutoff_hz", SMOOTHING_DEFAULTS["min_cutoff_hz"]
        ),
        "dwell.smoothing.beta": smoothing.get("beta", SMOOTHING_DEFAULTS["beta"]),
    }

