"""Which Gazepoint signal drives the cursor, and the smoothing types that follow it
(SPEC-gaze-stability-and-positioning.md 4.1-4.3, 4.9; Qt-free).

``dwell.pointer_signal`` is the card's "Cursor stabilisation" choice, two approaches; it never
touches the recorded raw gaze (``GazeSample.x`` / ``y`` / ``valid`` stay ``BPOG``, then ``FPOG``)::

    best       App smoothing (raw gaze): BPOG, falling back to FPOG when it is invalid, plus
               the app's own filter (below)
    assistive  Gazepoint Assistive: APOG only (a moving-window average of FPOG, length
               ``AAC_FILTER``); the app never smooths it on top (two averages in a row lag)

``fixation`` (FPOG only) is no longer offered (G9: it freezes during every eye movement, then
jumps). An old profile, config or hand edit that still says so loads as ``best`` and the run's
session log says so (:func:`retired_signal_note`).

``dwell.smoothing.type`` picks the app's filter for ``best``: the plain running average
(``ema``) or the speed-adaptive One Euro filter (``one_euro``).
"""

from __future__ import annotations

from typing import Any

SIGNAL_BEST = "best"
SIGNAL_ASSISTIVE = "assistive"
POINTER_SIGNALS = (SIGNAL_BEST, SIGNAL_ASSISTIVE)
DEFAULT_SIGNAL = SIGNAL_BEST
SIGNAL_LABELS = {
    SIGNAL_BEST: "App smoothing (raw gaze)",
    SIGNAL_ASSISTIVE: "Gazepoint Assistive (APOG)",
}
# Withdrawn at the live check (G9). Never offered or stored any more; kept to read an old
# session (the report) and for the FPOG branch of :func:`pointer_from_rec`.
SIGNAL_FIXATION = "fixation"
RETIRED_SIGNAL_LABELS = {SIGNAL_FIXATION: "Fixation (FPOG), no longer offered"}

SMOOTHING_EMA = "ema"
SMOOTHING_ONE_EURO = "one_euro"
SMOOTHING_TYPES = (SMOOTHING_EMA, SMOOTHING_ONE_EURO)
DEFAULT_SMOOTHING_TYPE = SMOOTHING_EMA
SMOOTHING_LABELS = {SMOOTHING_EMA: "Simple", SMOOTHING_ONE_EURO: "Adaptive (One Euro)"}

# AAC_FILTER: the APOG moving-window length in samples (API manual 3.22). 15 is the device's own.
AAC_FILTER_MIN = 1
AAC_FILTER_MAX = 60
AAC_FILTER_DEFAULT = 15

# One Euro starting values (the user's choice, 2026-10-13; still to be tuned at the live check,
# SPEC plan step 5) and ranges. They meet acceptance A3.
ONE_EURO_MIN_CUTOFF_DEFAULT = 0.3
ONE_EURO_MIN_CUTOFF_RANGE = (0.05, 5.0)
ONE_EURO_BETA_DEFAULT = 5.0
ONE_EURO_BETA_RANGE = (0.0, 10.0)


def normalize_signal(value: Any) -> str:
    """``value`` if it is an offered pointer signal, else the default: a hand-edited profile,
    and the retired ``fixation`` of an old one (G9)."""
    return value if value in POINTER_SIGNALS else DEFAULT_SIGNAL


def normalize_smoothing_type(value: Any) -> str:
    return value if value in SMOOTHING_TYPES else DEFAULT_SMOOTHING_TYPE


def signal_label(value: Any) -> str:
    """The signal's name on the card and in the report; the retired ``fixation`` keeps its own,
    so an old session still reads as what it was."""
    return RETIRED_SIGNAL_LABELS.get(value) or SIGNAL_LABELS[normalize_signal(value)]


def retired_signal_note(value: Any) -> str | None:
    """The session-log line for a retired signal that a profile or config still names (G9),
    ``None`` for anything else (the run itself already uses :func:`normalize_signal`)."""
    if value not in RETIRED_SIGNAL_LABELS:
        return None
    return f"Gaze signal '{value}' is no longer offered; using {SIGNAL_LABELS[DEFAULT_SIGNAL]}."


def app_smoothing_on(signal: Any, enabled: Any) -> bool:
    """Whether the app's own smoothing runs: ``enabled`` (``dwell.smoothing.enabled``) for App
    smoothing, never for Gazepoint Assistive, whatever ``enabled`` says (G10: Assistive plus the
    app's average is two averages in a row, which lags a lot). The saved smoothing settings are
    kept, so switching back to App smoothing restores them."""
    return bool(enabled) and normalize_signal(signal) != SIGNAL_ASSISTIVE


def smoothing_label(value: Any) -> str:
    return SMOOTHING_LABELS[normalize_smoothing_type(value)]


def clamp_aac_filter(value: Any) -> int:
    """``value`` as an integer window length within the device's range, the default when it
    is not a number."""
    try:
        samples = int(value)
    except (TypeError, ValueError):
        return AAC_FILTER_DEFAULT
    return max(AAC_FILTER_MIN, min(AAC_FILTER_MAX, samples))


def _float(attrs: dict[str, str], key: str) -> float | None:
    raw = attrs.get(key)
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def pointer_from_rec(
    attrs: dict[str, str], signal: str, best: tuple[float | None, float | None, bool]
) -> tuple[float, float, bool]:
    """``(x, y, valid)`` of the cursor's signal in one REC. ``best`` is what the record's
    raw gaze came to (BPOG, else FPOG), reused for ``best`` so that signal is the raw gaze
    exactly. A missing coordinate is ``0.0`` and never valid, like the raw gaze. The FPOG branch
    is internal: no setting reaches it any more (G9)."""
    if signal == SIGNAL_FIXATION:
        x, y, valid = _float(attrs, "FPOGX"), _float(attrs, "FPOGY"), attrs.get("FPOGV", "0") == "1"
    elif signal == SIGNAL_ASSISTIVE:
        x, y, valid = _float(attrs, "APOGX"), _float(attrs, "APOGY"), attrs.get("APOGV", "0") == "1"
    else:
        x, y, valid = best
    return (
        x if x is not None else 0.0,
        y if y is not None else 0.0,
        bool(valid and x is not None and y is not None),
    )


def apply_gaze_signal(
    client: Any, signal: str, aac_samples: int, requested: Any = None
) -> list[str]:
    """Set the cursor signal on a tracker at run start and return the session-log lines for
    it. ``requested`` is the signal as the config named it, before :func:`normalize_signal`
    (a retired one adds its note). A client without the methods (the mouse stand-in, a stub)
    is left alone and logs nothing about the signal. ``AAC_FILTER`` is sent only for
    ``assistive`` (SPEC 4.2); the client restores the device's own value on disconnect and
    close."""
    lines = []
    note = retired_signal_note(requested)
    if note:
        lines.append(note)
    set_signal = getattr(client, "set_pointer_signal", None)
    if set_signal is None:
        return lines
    set_signal(signal)
    lines.append(f"Gaze signal: {signal_label(signal)}.")
    set_filter = getattr(client, "set_aac_filter", None)
    if signal == SIGNAL_ASSISTIVE and set_filter is not None:
        n = clamp_aac_filter(aac_samples)
        if set_filter(n):
            lines.append(f"AAC filter set to {n} samples.")
        else:
            lines.append(f"WARNING: could not send AAC_FILTER {n} (tracker not connected).")
    return lines
