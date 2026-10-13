"""Head position for the operator: where the child's head sits in the tracker's head box
(SPEC-gaze-stability-and-positioning.md 4.5-4.6, wireframes ``setup.md`` / ``start-test.md``).

A pure, Qt-free model. The 3D eye positions the client already subscribes to
(``LEYEX/Y/Z``, ``REYEX/Y/Z``, metres from the camera focal point, plus the
``LPUPILV``/``RPUPILV`` validity flags) go in; out comes a :class:`HeadReading`: the face's
place in the head box, its size (distance) and tilt (head roll), a state (green, orange,
red, no eyes, not connected) and the hint text the operator reads. The widget that draws it
is :mod:`src.ui.head_position_widget`.

:func:`assess` is the instantaneous reading; :class:`HeadPositionTracker` adds the timing
rules of 4.6 (the colour changes only after about 0.3 s in the new state, "no eyes" only
after 0.5 s without one). Time is always passed in, so the rules are testable without a
clock.

The model gates nothing: it is information for the operator.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

# -- geometry and bands ------------------------------------------------------------------------
# Everything below that needs the device is a starting value, tuned at the live check
# (SPEC 4.5/4.6, probe P5): the signs of X and Y, the Y of a well-seated head, the bands.

HEAD_BOX_WIDTH_CM = 35.0  # GP3 HD tracking range (head box), docs/gazepoints/synthesis/gp3-hd-specifications.md
HEAD_BOX_HEIGHT_CM = 22.0

# Which way the face is drawn when a device value grows. +1: a larger X is drawn further right
# (the left eye has the negative X, so the face reads like a selfie camera: the child's left eye is
# on the left of the picture), a larger Y further down. Tuned at the live check (SPEC 4.5/4.6, probe P5).
DISPLAY_X_SIGN = 1.0
DISPLAY_Y_SIGN = 1.0

# The eye midpoint of a well-seated head, in cm, device axes. The camera sits below the screen, so
# "centred" is not Y = 0; measured, then stored here. Tuned at the live check (SPEC 4.5/4.6, probe P5).
CENTRED_X_CM = 0.0
CENTRED_Y_CM = 0.0

# With one eye valid the face centre is that eye moved half this far toward the other, so the face
# does not jump when an eye drops out. Tuned at the live check (SPEC 4.5/4.6, probe P5).
NOMINAL_EYE_SEPARATION_CM = 6.3

# Distance (Z, cm): green inside Z_GREEN, orange inside Z_ORANGE, red beyond. The Close-Far bar spans
# BAR_MIN_CM..BAR_MAX_CM. Tuned at the live check (SPEC 4.5/4.6, probe P5).
Z_GREEN_MIN_CM, Z_GREEN_MAX_CM = 55.0, 75.0
Z_ORANGE_MIN_CM, Z_ORANGE_MAX_CM = 50.0, 80.0
BAR_MIN_CM, BAR_MAX_CM = 45.0, 85.0

# The face centre is green inside this fraction of the head box (per axis), orange between it and
# the box edge, red outside the box. Tuned at the live check (SPEC 4.5/4.6, probe P5).
CENTRE_INNER_FRACTION = 0.70

# The face is drawn at FACE_SCALE = 1 at this distance and scales with 1 / distance.
FACE_REFERENCE_CM = 65.0
FACE_SCALE_MIN, FACE_SCALE_MAX = 0.5, 1.6
_FACE_POSITION_LIMIT = 1.25  # the face centre stays within this far of the box (fractions), whatever the data

# -- timing (4.6) ---------------------------------------------------------------------------------

STATE_HOLD_S = 0.3  # a new colour or hint shows only after it has held this long
NO_EYES_DELAY_S = 0.5  # neither eye for this long before "No eyes detected"
STALE_AFTER_S = 1.0  # eye data older than this (a stopped or paused stream) counts as no eyes

# -- the words the operator reads -------------------------------------------------------------------

HINT_GOOD = "Good position"
HINT_TOO_CLOSE = "Move back"  # under the green band: nearer the tracker than 55 cm
HINT_TOO_FAR = "Move closer"  # over the green band: further from the tracker than 75 cm
HINT_LEFT = "Move left"
HINT_RIGHT = "Move right"
HINT_UP = "Move up"
HINT_DOWN = "Move down"
HINT_ONE_EYE = "Only one eye seen"  # orange with no position fault (SPEC 4.6, user choice 2026-10-13)
HINT_NO_EYES = "No eyes detected"
HINT_NOT_CONNECTED = "Tracker not connected"


class HeadState(StrEnum):
    GREEN = "green"
    ORANGE = "orange"
    RED = "red"
    NO_EYES = "no_eyes"
    NOT_CONNECTED = "not_connected"


# Whether the state shows a face (the other two show an empty box).
FACE_STATES = (HeadState.GREEN, HeadState.ORANGE, HeadState.RED)


@dataclass(frozen=True, slots=True)
class EyePosition:
    """One REC's 3D eye positions. ``left`` / ``right`` are ``(x, y, z)`` in metres from the
    camera focal point, ``None`` when that eye is not valid (its ``*PUPILV`` flag is 0, or the
    coordinates are missing). ``received_s`` is ``time.monotonic()`` at receipt."""

    left: tuple[float, float, float] | None
    right: tuple[float, float, float] | None
    received_s: float


def _eye(attrs: dict[str, str], prefix: str) -> tuple[float, float, float] | None:
    if attrs.get(f"{prefix}PUPILV", "0") != "1":
        return None
    try:
        x, y, z = (float(attrs[f"{prefix}EYE{axis}"]) for axis in "XYZ")
    except (KeyError, ValueError):
        return None
    # A device that reports "no eye" can send zeros: a distance of 0 is never a real eye.
    return (x, y, z) if z > 0.0 and all(map(math.isfinite, (x, y, z))) else None


def eye_position_from_attrs(attrs: dict[str, str], received_s: float) -> EyePosition | None:
    """The eye positions of a parsed ``<REC>``; ``None`` when it carries none (the eye records
    are switched off, or a replay fixture without them)."""
    if "LEYEX" not in attrs and "REYEX" not in attrs:
        return None
    return EyePosition(_eye(attrs, "L"), _eye(attrs, "R"), received_s)


@dataclass(frozen=True, slots=True)
class HeadReading:
    """What the widget shows. ``face_u`` / ``face_v`` are the face centre in the head box as
    fractions, 0 left / top to 1 right / bottom (outside 0-1 when the head is outside the box);
    ``face_scale`` is 1 at :data:`FACE_REFERENCE_CM`; ``roll_deg`` is the tilt, positive
    clockwise on screen. ``centre_x_cm`` / ``centre_y_cm`` are the eye midpoint's offset from the
    centred position on the device's axes."""

    state: HeadState
    hint: str
    z_cm: float | None = None
    centre_x_cm: float | None = None
    centre_y_cm: float | None = None
    face_u: float = 0.5
    face_v: float = 0.5
    face_scale: float = 1.0
    roll_deg: float = 0.0

    @property
    def has_face(self) -> bool:
        return self.state in FACE_STATES

    def status_text(self) -> str:
        """The one status line: the hint and, when there is a face, the distance."""
        if self.has_face and self.z_cm is not None:
            return f"{self.hint}, {self.z_cm:.0f} cm"
        return self.hint

    def as_metadata(self) -> dict[str, object]:
        """``metadata.json``'s ``head_position_at_start`` (4.7): the state, Z in cm and the centre
        offset in cm, each ``None`` when there were no eyes to measure."""
        return {
            "state": self.state.value,
            "z_cm": None if self.z_cm is None else round(self.z_cm, 1),
            "centre_x_cm": None if self.centre_x_cm is None else round(self.centre_x_cm, 1),
            "centre_y_cm": None if self.centre_y_cm is None else round(self.centre_y_cm, 1),
        }


NOT_CONNECTED = HeadReading(HeadState.NOT_CONNECTED, HINT_NOT_CONNECTED)
NO_EYES = HeadReading(HeadState.NO_EYES, HINT_NO_EYES)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _in_box(offset_cm: float, extent_cm: float) -> float:
    """A display offset from the box centre as a fraction of the box (0.5 is the centre)."""
    return _clamp(0.5 + offset_cm / extent_cm, -_FACE_POSITION_LIMIT, 1.0 + _FACE_POSITION_LIMIT)


def assess(eyes: EyePosition | None, now_s: float) -> HeadReading:
    """The reading for one eye position, with no timing rules: ``NO_EYES`` when neither eye is
    valid or the data is stale; otherwise a face placed in the head box and its state (4.6)."""
    if eyes is None or now_s - eyes.received_s > STALE_AFTER_S:
        return NO_EYES
    left, right = eyes.left, eyes.right
    if left is None and right is None:
        return NO_EYES

    # Eye midpoint and distance, in cm. One eye: the centre is that eye moved half the nominal
    # separation toward where the other would be.
    if left is not None and right is not None:
        x_cm, y_cm, z_cm = ((a + b) * 50.0 for a, b in zip(left, right, strict=True))
    else:
        eye, toward_other = (left, 1.0) if left is not None else (right, -1.0)
        x_cm = eye[0] * 100.0 + toward_other * NOMINAL_EYE_SEPARATION_CM / 2.0
        y_cm, z_cm = eye[1] * 100.0, eye[2] * 100.0
    centre_x = x_cm - CENTRED_X_CM
    centre_y = y_cm - CENTRED_Y_CM

    # Where the face is drawn (the display's own axes, signs from the constants above).
    face_u = _in_box(DISPLAY_X_SIGN * centre_x, HEAD_BOX_WIDTH_CM)
    face_v = _in_box(DISPLAY_Y_SIGN * centre_y, HEAD_BOX_HEIGHT_CM)
    scale = _clamp(FACE_REFERENCE_CM / z_cm, FACE_SCALE_MIN, FACE_SCALE_MAX)

    roll_deg = 0.0
    if left is not None and right is not None:
        # The line between the eyes in display axes, read left to right whichever way the signs run.
        (x1, y1), (x2, y2) = sorted(
            ((DISPLAY_X_SIGN * eye[0], DISPLAY_Y_SIGN * eye[1]) for eye in (left, right)),
            key=lambda point: point[0],
        )
        roll_deg = math.degrees(math.atan2(y2 - y1, x2 - x1))

    # Faults, each normalised so 0 is the edge of green and 1 the edge of red; the largest is the
    # hint, and its size the colour. The hint names the way to move on the picture.
    faults: list[tuple[float, str]] = []
    if z_cm < Z_GREEN_MIN_CM:
        faults.append(((Z_GREEN_MIN_CM - z_cm) / (Z_GREEN_MIN_CM - Z_ORANGE_MIN_CM), HINT_TOO_CLOSE))
    elif z_cm > Z_GREEN_MAX_CM:
        faults.append(((z_cm - Z_GREEN_MAX_CM) / (Z_ORANGE_MAX_CM - Z_GREEN_MAX_CM), HINT_TOO_FAR))
    for offset_cm, half_cm, hint_if_negative, hint_if_positive in (
        (DISPLAY_X_SIGN * centre_x, HEAD_BOX_WIDTH_CM / 2.0, HINT_RIGHT, HINT_LEFT),
        (DISPLAY_Y_SIGN * centre_y, HEAD_BOX_HEIGHT_CM / 2.0, HINT_DOWN, HINT_UP),
    ):
        inner_cm = CENTRE_INNER_FRACTION * half_cm
        if abs(offset_cm) > inner_cm:
            hint_here = hint_if_positive if offset_cm > 0 else hint_if_negative
            faults.append(((abs(offset_cm) - inner_cm) / (half_cm - inner_cm), hint_here))
    severity, hint = max(faults, key=lambda fault: fault[0]) if faults else (0.0, "")

    both = left is not None and right is not None
    if severity > 1.0:
        state = HeadState.RED
    elif severity > 0.0 or not both:
        state = HeadState.ORANGE
    else:
        state = HeadState.GREEN
    if not hint:
        hint = HINT_GOOD if both else HINT_ONE_EYE
    return HeadReading(
        state=state,
        hint=hint,
        z_cm=z_cm,
        centre_x_cm=centre_x,
        centre_y_cm=centre_y,
        face_u=face_u,
        face_v=face_v,
        face_scale=scale,
        roll_deg=roll_deg,
    )


class HeadPositionTracker:
    """The timing rules of 4.6 over :func:`assess`. Feed it every poll with the time; it returns
    the reading to show.

    * A new colour or hint (the state and hint as a pair) shows only once the same one has been
      raw for :data:`STATE_HOLD_S`, so it does not flicker at a boundary. The face and the
      distance follow the data at once.
    * "No eyes" shows only after :data:`NO_EYES_DELAY_S` without one, so a blink never blanks the
      box; until then the last reading stays up.
    * A reading after "no eyes" or "not connected" shows at once: there is nothing to flicker
      against.
    * "Not connected" shows at once.
    """

    def __init__(self) -> None:
        self._shown: HeadReading | None = None
        self._pending: HeadReading | None = None  # the raw state/hint waiting out its hold
        self._pending_since = 0.0
        self._eyes_lost_since: float | None = None

    @property
    def reading(self) -> HeadReading | None:
        """The reading shown now; ``None`` before the first :meth:`update`."""
        return self._shown

    def reset(self) -> None:
        self.__init__()

    def update(self, connected: bool, eyes: EyePosition | None, now_s: float) -> HeadReading:
        if not connected:
            self.reset()
            self._shown = NOT_CONNECTED
            return NOT_CONNECTED
        raw = assess(eyes, now_s)
        shown = self._shown
        if raw.state is HeadState.NO_EYES:
            if shown is None or shown.state in (HeadState.NO_EYES, HeadState.NOT_CONNECTED):
                self._shown = NO_EYES
            else:
                if self._eyes_lost_since is None:
                    self._eyes_lost_since = now_s
                if now_s - self._eyes_lost_since >= NO_EYES_DELAY_S:
                    self._shown = NO_EYES
            self._pending = None
            return self._shown
        self._eyes_lost_since = None
        if shown is None or not shown.has_face:
            self._pending = None
            self._shown = raw
            return raw
        if (raw.state, raw.hint) == (shown.state, shown.hint):
            self._pending = None
            self._shown = raw
            return raw
        if self._pending is None or (self._pending.state, self._pending.hint) != (raw.state, raw.hint):
            self._pending, self._pending_since = raw, now_s
        if now_s - self._pending_since >= STATE_HOLD_S:
            self._pending = None
            self._shown = raw
            return raw
        # Still the old colour and words, the face and the distance on the new data.
        self._shown = _with_old_words(raw, shown)
        return self._shown


def _with_old_words(raw: HeadReading, shown: HeadReading) -> HeadReading:
    """``raw``'s face and numbers under ``shown``'s state and hint."""
    return HeadReading(
        state=shown.state,
        hint=shown.hint,
        z_cm=raw.z_cm,
        centre_x_cm=raw.centre_x_cm,
        centre_y_cm=raw.centre_y_cm,
        face_u=raw.face_u,
        face_v=raw.face_v,
        face_scale=raw.face_scale,
        roll_deg=raw.roll_deg,
    )

