"""SPEC-gaze-stability-and-positioning.md 4.5-4.6, acceptance A8: the head-position model.
Eye 3D position -> where the face sits in the head box, its size and tilt, the colour state
and the hint, and the timing rules (0.3 s colour hold, 0.5 s "no eyes"). Pure and Qt-free.

The tests build heads from the model's own centre and signs (``DISPLAY_*_SIGN``,
``CENTRED_*_CM``), so a live-check retune of those constants does not break them; the bands
(55-75 cm and so on) are the SPEC's and are asserted as written."""

from __future__ import annotations

import math
import time

import pytest

from src.inputs import head_position as hp
from src.inputs.gazepoint_client import GazepointClient, parse_rec, rec_to_sample
from src.inputs.head_position import (
    EyePosition,
    HeadPositionTracker,
    HeadState,
    assess,
    eye_position_from_attrs,
)

from .test_gazepoint_client import _wait_until, fake_server  # noqa: F401  (fixture)

GREEN, ORANGE, RED = HeadState.GREEN, HeadState.ORANGE, HeadState.RED
SEPARATION_M = 0.06


def eyes(dx_cm=0.0, dy_cm=0.0, z_cm=65.0, *, tilt_cm=0.0, at=0.0, left=True, right=True):
    """A head ``dx_cm`` / ``dy_cm`` from the centred position (device axes), ``z_cm`` from the
    tracker, the eyes 6 cm apart; ``tilt_cm`` raises the right eye's Y and lowers the left's by
    that much; ``left`` / ``right`` say which eyes are valid."""
    cx = (hp.CENTRED_X_CM + dx_cm) / 100.0
    cy = (hp.CENTRED_Y_CM + dy_cm) / 100.0
    z = z_cm / 100.0
    return EyePosition(
        (cx - SEPARATION_M / 2, cy - tilt_cm / 100.0, z) if left else None,
        (cx + SEPARATION_M / 2, cy + tilt_cm / 100.0, z) if right else None,
        at,
    )


# -- the REC fields --------------------------------------------------------------------------


REC = (
    '<REC LEYEX="-0.03000" LEYEY="0.01000" LEYEZ="0.65000" LPUPILD="0.00300" LPUPILV="1" '
    'REYEX="0.03000" REYEY="0.02000" REYEZ="0.66000" RPUPILD="0.00300" RPUPILV="1" />'
)


def test_a_rec_with_both_eyes_gives_both_positions_and_the_receipt_time():
    position = eye_position_from_attrs(parse_rec(REC), 12.5)
    assert position == EyePosition((-0.03, 0.01, 0.65), (0.03, 0.02, 0.66), 12.5)


def test_an_eye_with_its_valid_flag_at_zero_is_none():
    position = eye_position_from_attrs(parse_rec(REC.replace('LPUPILV="1"', 'LPUPILV="0"')), 0.0)
    assert position.left is None and position.right == (0.03, 0.02, 0.66)


def test_zeros_are_never_a_real_eye_even_when_flagged_valid():
    position = eye_position_from_attrs(
        parse_rec(REC.replace('LEYEZ="0.65000"', 'LEYEZ="0.00000"')), 0.0
    )
    assert position.left is None and position.right is not None


def test_a_rec_without_the_eye_fields_has_no_position():
    assert eye_position_from_attrs(parse_rec('<REC BPOGX="0.5" BPOGY="0.5" BPOGV="1" />'), 0.0) is None


def test_unparsable_coordinates_make_that_eye_invalid_not_an_error():
    position = eye_position_from_attrs(parse_rec(REC.replace('REYEY="0.02000"', 'REYEY="x"')), 0.0)
    assert position.left is not None and position.right is None


# -- position, size, tilt (4.5) ------------------------------------------------------------------


def test_a_centred_head_puts_the_face_in_the_middle_at_full_size_without_tilt():
    reading = assess(eyes(), 0.0)
    assert (reading.face_u, reading.face_v) == pytest.approx((0.5, 0.5))
    assert reading.face_scale == pytest.approx(1.0)
    assert reading.roll_deg == pytest.approx(0.0)
    assert reading.z_cm == pytest.approx(65.0)
    assert (reading.centre_x_cm, reading.centre_y_cm) == pytest.approx((0.0, 0.0))


def test_the_face_moves_with_the_midpoint_of_the_eyes_by_the_box_fraction():
    reading = assess(eyes(dx_cm=7.0, dy_cm=-4.4), 0.0)
    assert reading.face_u == pytest.approx(0.5 + hp.DISPLAY_X_SIGN * 7.0 / hp.HEAD_BOX_WIDTH_CM)
    assert reading.face_v == pytest.approx(0.5 + hp.DISPLAY_Y_SIGN * -4.4 / hp.HEAD_BOX_HEIGHT_CM)
    assert (reading.centre_x_cm, reading.centre_y_cm) == pytest.approx((7.0, -4.4))


def test_a_head_far_outside_the_box_keeps_the_face_within_a_bounded_distance_of_it():
    reading = assess(eyes(dx_cm=300.0, dy_cm=-300.0), 0.0)
    assert -1.5 <= reading.face_u <= 2.5 and -1.5 <= reading.face_v <= 2.5


@pytest.mark.parametrize(
    "z_cm, scale",
    [(65.0, 1.0), (50.0, 1.3), (80.0, 65.0 / 80.0), (20.0, hp.FACE_SCALE_MAX), (400.0, hp.FACE_SCALE_MIN)],
)
def test_the_face_grows_when_close_and_shrinks_when_far_within_limits(z_cm, scale):
    assert assess(eyes(z_cm=z_cm), 0.0).face_scale == pytest.approx(scale)


def test_the_distance_is_the_mean_of_the_two_eyes():
    both = EyePosition((-0.03, 0.0, 0.62), (0.03, 0.0, 0.66), 0.0)
    assert assess(both, 0.0).z_cm == pytest.approx(64.0)


def test_the_face_tilts_with_the_line_between_the_eyes():
    # 2 cm of Y between eyes 6 cm apart: atan(2 / 6) = 18.4 degrees, clockwise when the eye on
    # the right of the picture is the lower one.
    tilted = assess(eyes(tilt_cm=1.0), 0.0).roll_deg
    assert abs(tilted) == pytest.approx(math.degrees(math.atan2(2.0, 6.0)))
    assert (tilted > 0) == (hp.DISPLAY_X_SIGN * hp.DISPLAY_Y_SIGN > 0)
    # Swapping the eyes' heights flips the tilt.
    assert assess(eyes(tilt_cm=-1.0), 0.0).roll_deg == pytest.approx(-tilted)


def test_the_tilt_is_read_left_to_right_whichever_way_the_signs_run(monkeypatch):
    base = assess(eyes(tilt_cm=1.0), 0.0).roll_deg
    monkeypatch.setattr(hp, "DISPLAY_X_SIGN", -hp.DISPLAY_X_SIGN)
    assert abs(assess(eyes(tilt_cm=1.0), 0.0).roll_deg) < 90.0  # not a half turn
    assert abs(assess(eyes(tilt_cm=1.0), 0.0).roll_deg) == pytest.approx(abs(base))


# -- the state and the hint (4.6) -------------------------------------------------------------------


def move(direction_in_picture: str, dx_cm=0.0, dy_cm=0.0) -> tuple[float, float]:
    """The device-axes offset that draws the face to the ``right`` / ``left`` / ``down`` /
    ``up`` of the picture centre by that many cm."""
    if direction_in_picture in ("right", "left"):
        sign = hp.DISPLAY_X_SIGN * (1 if direction_in_picture == "right" else -1)
        return sign * dx_cm, 0.0
    sign = hp.DISPLAY_Y_SIGN * (1 if direction_in_picture == "down" else -1)
    return 0.0, sign * dy_cm


@pytest.mark.parametrize(
    "z_cm, state, hint",
    [
        (65.0, GREEN, "Good position"),
        (55.5, GREEN, "Good position"),
        (74.5, GREEN, "Good position"),
        (54.5, ORANGE, "Move back"),  # nearer than the green band: back away from the tracker
        (51.0, ORANGE, "Move back"),
        (49.5, RED, "Move back"),
        (75.5, ORANGE, "Move closer"),
        (79.0, ORANGE, "Move closer"),
        (80.5, RED, "Move closer"),
    ],
)
def test_the_distance_bands_give_the_colour_and_the_hint(z_cm, state, hint):
    reading = assess(eyes(z_cm=z_cm), 0.0)
    assert (reading.state, reading.hint) == (state, hint)


@pytest.mark.parametrize(
    "way, cm, state, hint",
    [
        ("right", 12.0, GREEN, "Good position"),  # inner 70 % of 35 cm is +-12.25 cm
        ("right", 13.0, ORANGE, "Move left"),  # drawn to the right: move left in the picture
        ("left", 13.0, ORANGE, "Move right"),
        ("right", 17.0, ORANGE, "Move left"),
        ("right", 18.0, RED, "Move left"),  # beyond the box edge (17.5 cm)
        ("left", 18.0, RED, "Move right"),
    ],
)
def test_the_sideways_bands_give_the_colour_and_the_hint(way, cm, state, hint):
    dx, _ = move(way, dx_cm=cm)
    reading = assess(eyes(dx_cm=dx), 0.0)
    assert (reading.state, reading.hint) == (state, hint)


@pytest.mark.parametrize(
    "way, cm, state, hint",
    [
        ("down", 7.0, GREEN, "Good position"),  # inner 70 % of 22 cm is +-7.7 cm
        ("down", 8.5, ORANGE, "Move up"),
        ("up", 8.5, ORANGE, "Move down"),
        ("down", 11.5, RED, "Move up"),  # beyond the box edge (11 cm)
        ("up", 11.5, RED, "Move down"),
    ],
)
def test_the_vertical_bands_give_the_colour_and_the_hint(way, cm, state, hint):
    _, dy = move(way, dy_cm=cm)
    reading = assess(eyes(dy_cm=dy), 0.0)
    assert (reading.state, reading.hint) == (state, hint)


def test_the_largest_fault_gives_the_hint_and_the_colour():
    dx, _ = move("right", dx_cm=16.0)  # 0.71 of the way from green to red
    # Distance 53 cm is 0.4 of the way: the sideways fault is larger.
    reading = assess(eyes(dx_cm=dx, z_cm=53.0), 0.0)
    assert (reading.state, reading.hint) == (ORANGE, "Move left")
    # Distance 51 cm is 0.8 of the way: now the distance is the larger fault.
    assert assess(eyes(dx_cm=dx, z_cm=51.0), 0.0).hint == "Move back"
    # One red fault makes the whole thing red, whatever else is only orange.
    assert assess(eyes(dx_cm=dx, z_cm=48.0), 0.0).state == RED


def test_one_eye_only_is_orange_and_keeps_the_face_where_the_head_is():
    assert hp.HINT_ONE_EYE == "Only one eye seen"  # the user's wording (SPEC 4.6)
    for kept in ({"left": True, "right": False}, {"left": False, "right": True}):
        reading = assess(eyes(**kept), 0.0)
        assert reading.state == ORANGE and reading.hint == hp.HINT_ONE_EYE
        # The centre is that eye moved half the nominal separation (6.3 cm) toward the other,
        # so it is within 0.15 cm of where two eyes 6 cm apart put it and does not jump.
        error_cm = hp.NOMINAL_EYE_SEPARATION_CM / 2.0 - SEPARATION_M * 50.0
        assert reading.centre_x_cm == pytest.approx(error_cm if kept["left"] else -error_cm)
        assert reading.roll_deg == 0.0
        assert reading.z_cm == pytest.approx(65.0)


def test_one_eye_with_a_position_fault_names_the_fault_and_a_big_one_is_red():
    assert assess(eyes(z_cm=53.0, right=False), 0.0).hint == "Move back"
    assert assess(eyes(z_cm=45.0, left=False), 0.0).state == RED


def test_no_valid_eye_is_no_eyes_and_so_is_missing_or_stale_data():
    assert assess(eyes(left=False, right=False), 0.0) is hp.NO_EYES
    assert assess(None, 0.0) is hp.NO_EYES
    assert assess(eyes(at=0.0), hp.STALE_AFTER_S + 0.01) is hp.NO_EYES  # the stream stopped
    assert assess(eyes(at=0.0), hp.STALE_AFTER_S - 0.01).state == GREEN


def test_the_words_the_operator_reads():
    assert hp.assess(eyes(), 0.0).status_text() == "Good position, 65 cm"
    assert assess(eyes(z_cm=52.0), 0.0).status_text() == "Move back, 52 cm"
    assert hp.NO_EYES.status_text() == "No eyes detected"
    assert hp.NOT_CONNECTED.status_text() == "Tracker not connected"
    assert (hp.NO_EYES.has_face, hp.NOT_CONNECTED.has_face) == (False, False)


def test_the_metadata_form_is_the_state_the_distance_and_the_centre_offset():
    reading = assess(eyes(dx_cm=2.04, dy_cm=-1.26, z_cm=64.26), 0.0)
    assert reading.as_metadata() == {
        "state": "green", "z_cm": 64.3, "centre_x_cm": 2.0, "centre_y_cm": -1.3,
    }
    assert hp.NO_EYES.as_metadata() == {
        "state": "no_eyes", "z_cm": None, "centre_x_cm": None, "centre_y_cm": None,
    }
    assert hp.NOT_CONNECTED.as_metadata()["state"] == "not_connected"


# -- the timing rules (4.6) ----------------------------------------------------------------------------


def run(tracker, frames):
    """Feed ``(t, eyes_or_None, connected)`` frames; the readings shown."""
    return [tracker.update(connected, e, t) for t, e, connected in frames]


def fresh(e, t):
    """``e`` as received at ``t``, so it is never stale."""
    return EyePosition(e.left, e.right, t)


def test_the_first_reading_shows_at_once():
    tracker = HeadPositionTracker()
    assert tracker.reading is None
    assert tracker.update(True, eyes(z_cm=52.0), 0.0).state == ORANGE


def test_a_new_colour_shows_only_after_0_3_s_and_the_face_follows_the_data_meanwhile():
    tracker = HeadPositionTracker()
    tracker.update(True, eyes(z_cm=65.0, at=0.0), 0.0)
    early = tracker.update(True, eyes(z_cm=54.0, at=0.1), 0.1)  # raw: orange "Move back"
    assert (early.state, early.hint) == (GREEN, "Good position")
    assert early.z_cm == pytest.approx(54.0)  # the distance and face already follow
    assert tracker.update(True, eyes(z_cm=54.0, at=0.399), 0.399).state == GREEN
    late = tracker.update(True, eyes(z_cm=54.0, at=0.4), 0.4)  # 0.3 s after it began
    assert (late.state, late.hint) == (ORANGE, "Move back")


def test_a_boundary_flicker_never_changes_the_colour():
    tracker = HeadPositionTracker()
    tracker.update(True, eyes(z_cm=56.0, at=0.0), 0.0)
    shown = []
    for i in range(1, 40):  # 0.05 s frames: 54 and 56 cm alternate every frame
        z = 54.0 if i % 2 else 56.0
        shown.append(tracker.update(True, eyes(z_cm=z, at=i * 0.05), i * 0.05).state)
    assert set(shown) == {GREEN}


def test_a_raw_state_that_does_not_last_does_not_restart_from_the_old_clock():
    tracker = HeadPositionTracker()
    tracker.update(True, eyes(z_cm=65.0, at=0.0), 0.0)
    tracker.update(True, eyes(z_cm=54.0, at=0.0), 0.0)  # orange starts
    tracker.update(True, eyes(z_cm=65.0, at=0.2), 0.2)  # back to green: the wait is cancelled
    assert tracker.update(True, eyes(z_cm=54.0, at=0.3), 0.3).state == GREEN  # a new wait begins
    assert tracker.update(True, eyes(z_cm=54.0, at=0.55), 0.55).state == GREEN  # 0.25 s into it
    assert tracker.update(True, eyes(z_cm=54.0, at=0.61), 0.61).state == ORANGE  # 0.31 s


def test_a_new_hint_within_the_same_colour_is_held_as_well():
    tracker = HeadPositionTracker()
    tracker.update(True, eyes(z_cm=54.0, at=0.0), 0.0)  # orange, Move back
    dx, _ = move("right", dx_cm=17.0)
    mid = tracker.update(True, eyes(dx_cm=dx, z_cm=65.0, at=0.1), 0.1)  # orange, Move left
    assert mid.hint == "Move back"
    assert tracker.update(True, eyes(dx_cm=dx, z_cm=65.0, at=0.4), 0.4).hint == "Move left"


def test_no_eyes_shows_only_after_0_5_s_and_until_then_the_last_reading_stays():
    tracker = HeadPositionTracker()
    before = tracker.update(True, eyes(at=0.0), 0.0)
    assert tracker.update(True, eyes(left=False, right=False, at=0.1), 0.1) == before
    assert tracker.update(True, eyes(left=False, right=False, at=0.59), 0.59) == before
    assert tracker.update(True, eyes(left=False, right=False, at=0.61), 0.61) is hp.NO_EYES


def test_a_blink_shorter_than_0_5_s_never_blanks_the_box():
    tracker = HeadPositionTracker()
    tracker.update(True, eyes(at=0.0), 0.0)
    states = [tracker.update(True, eyes(left=False, right=False, at=t), t).state for t in (0.1, 0.2, 0.3, 0.4)]
    states.append(tracker.update(True, eyes(at=0.45), 0.45).state)
    assert set(states) == {GREEN}
    # And the 0.5 s count starts over for the next loss.
    assert tracker.update(True, eyes(left=False, right=False, at=1.0), 1.0).state == GREEN
    assert tracker.update(True, eyes(left=False, right=False, at=1.3), 1.3).state == GREEN


def test_the_eyes_coming_back_show_at_once_even_in_a_new_colour():
    tracker = HeadPositionTracker()
    tracker.update(True, eyes(at=0.0), 0.0)
    tracker.update(True, eyes(left=False, right=False, at=0.1), 0.1)
    assert tracker.update(True, eyes(left=False, right=False, at=0.7), 0.7) is hp.NO_EYES
    assert tracker.update(True, eyes(z_cm=52.0, at=0.71), 0.71).state == ORANGE  # no 0.3 s wait


def test_no_eyes_with_nothing_before_it_shows_at_once():
    assert HeadPositionTracker().update(True, None, 0.0) is hp.NO_EYES


def test_stale_data_counts_as_no_eyes_after_the_delay():
    tracker = HeadPositionTracker()
    tracker.update(True, eyes(at=0.0), 0.0)  # the stream then stops
    assert tracker.update(True, eyes(at=0.0), 1.0).state == GREEN  # not stale yet
    assert tracker.update(True, eyes(at=0.0), 1.2).state == GREEN  # stale, 0 s without eyes
    assert tracker.update(True, eyes(at=0.0), 1.65).state == GREEN  # 0.45 s
    assert tracker.update(True, eyes(at=0.0), 1.71) is hp.NO_EYES  # over 0.5 s


def test_not_connected_shows_at_once_and_a_reconnect_shows_the_eyes_at_once():
    tracker = HeadPositionTracker()
    tracker.update(True, eyes(at=0.0), 0.0)
    assert tracker.update(False, None, 0.05) is hp.NOT_CONNECTED
    assert tracker.update(True, eyes(z_cm=52.0, at=0.06), 0.06).state == ORANGE


# -- the client's accessor -------------------------------------------------------------------------


def test_the_client_keeps_the_latest_eye_position_apart_from_the_gaze_sample():
    client = GazepointClient()
    assert client.latest_eye_position() is None
    attrs = parse_rec(REC)
    client._set_latest(rec_to_sample(attrs, 1), attrs)
    got = client.latest_eye_position()
    assert (got.left, got.right) == ((-0.03, 0.01, 0.65), (0.03, 0.02, 0.66))
    # A REC without eye fields leaves the last position (its age says it is old).
    plain = parse_rec('<REC BPOGX="0.5" BPOGY="0.5" BPOGV="1" />')
    client._set_latest(rec_to_sample(plain, 2), plain)
    assert client.latest_eye_position() is got
    # Once the link is lost it is not the child's any more.
    client._clear_latest()
    assert client.latest_eye_position() is None


def test_a_live_client_reads_the_eye_position_off_the_socket(fake_server):  # noqa: F811
    client = GazepointClient()
    client.connect(host="127.0.0.1", port=fake_server.port)
    client.start_streaming()
    try:
        fake_server.wait_for_connection()
        fake_server._conn.sendall((REC + "\n").encode("ascii"))
        assert _wait_until(lambda: client.latest_eye_position() is not None, timeout_s=3.0)
        got = client.latest_eye_position()
        assert (got.left, got.right) == ((-0.03, 0.01, 0.65), (0.03, 0.02, 0.66))
        assert 0.0 <= time.monotonic() - got.received_s < 3.0
    finally:
        client.stop()
    assert client.latest_eye_position() is None
