"""The One Euro filter and its place in GazeSmoother (SPEC-gaze-stability-and-positioning.md
4.3, A1, A3)."""

from __future__ import annotations

import random
import statistics

import pytest

from src.data.schema import GazeSample
from src.inputs.eye_input import EyeInput, GazeSmoother, SmoothingConfig
from src.inputs.one_euro import OneEuroFilter

RATE_HZ = 150
DT_NS = round(1e9 / RATE_HZ)


def _euro(**kw) -> GazeSmoother:
    return GazeSmoother(SmoothingConfig(type="one_euro", **kw))


# The starting defaults (SPEC 4.3: 0.3 Hz, beta 5.0; tuned further at the live check) are what A3 is
# checked against.


def test_the_starting_defaults_are_steadiness_0_3_hz_and_responsiveness_5():
    assert (SmoothingConfig().min_cutoff_hz, SmoothingConfig().beta) == (0.3, 5.0)
    f = OneEuroFilter()
    assert (f.min_cutoff_hz, f.beta) == (0.3, 5.0)


def test_the_first_point_passes_through_and_reset_starts_fresh():
    f = OneEuroFilter()
    assert f.update(0.3, 0.7, 0) == (0.3, 0.7)
    f.update(0.3, 0.7, DT_NS)
    f.reset()
    assert f.update(0.9, 0.1, 2 * DT_NS) == (0.9, 0.1)


def test_a_call_at_or_before_the_last_time_returns_the_last_point_unchanged():
    f = OneEuroFilter()
    f.update(0.2, 0.2, 1_000_000)
    first = f.update(0.4, 0.4, 1_000_000 + DT_NS)
    assert f.update(0.9, 0.9, 1_000_000 + DT_NS) == first  # same instant: no division by zero
    assert f.update(0.9, 0.9, 5) == first  # an earlier one


def test_the_output_stays_between_the_previous_output_and_the_input():
    f = OneEuroFilter()
    f.update(0.5, 0.5, 0)
    x, y = f.update(0.8, 0.2, DT_NS)
    assert 0.5 < x < 0.8 and 0.2 < y < 0.5


def test_a_longer_gap_between_samples_follows_the_input_more_closely():
    """The filter uses the real time between frames: the same step, seen after a longer wait, has
    moved further than after a shorter one."""
    near, far = OneEuroFilter(), OneEuroFilter()
    for f in (near, far):
        f.update(0.0, 0.0, 0)
    short = near.update(1.0, 0.0, DT_NS)[0]
    long = far.update(1.0, 0.0, 10 * DT_NS)[0]
    assert long > short


def test_the_smoother_needs_the_time_of_a_sample_for_one_euro_only():
    with pytest.raises(ValueError):
        _euro().update(0.5, 0.5)
    assert GazeSmoother(SmoothingConfig(enabled=True, alpha=0.35)).update(0.5, 0.5) == (0.5, 0.5)


def test_disabled_one_euro_passes_the_raw_value_through():
    smoother = GazeSmoother(SmoothingConfig(enabled=False, type="one_euro"))
    smoother.update(0.5, 0.5, 0)
    assert smoother.update(0.9, 0.1, DT_NS) == (0.9, 0.1)


def test_a3_at_rest_the_spread_is_at_most_a_quarter_of_the_ema():
    rng = random.Random(7)
    euro, ema = _euro(), GazeSmoother(SmoothingConfig(enabled=True, alpha=0.35))
    out_euro, out_ema = [], []
    for i in range(3000):
        x = 0.5 + rng.uniform(-0.005, 0.005)  # 0.5 % jitter
        out_euro.append(euro.update(x, x, i * DT_NS)[0])
        out_ema.append(ema.update(x, x)[0])
    spread_euro = statistics.pstdev(out_euro[500:])
    spread_ema = statistics.pstdev(out_ema[500:])
    assert spread_euro <= spread_ema / 4
    assert abs(statistics.mean(out_euro[500:]) - 0.5) < 0.005  # and still centred on the truth


def test_a3_after_a_step_jump_it_reaches_95_percent_within_150_ms():
    euro = _euro()
    for i in range(300):
        euro.update(0.2, 0.2, i * DT_NS)  # at rest first
    reached = None
    for i in range(1, 60):
        x = euro.update(0.5, 0.2, (300 + i) * DT_NS)[0]
        if x >= 0.2 + 0.95 * 0.3:
            reached = i * DT_NS / 1e9
            break
    assert reached is not None and reached <= 0.15


def test_the_steadier_setting_is_steadier_and_the_more_responsive_one_catches_up_faster():
    rng = random.Random(3)
    noise = [rng.uniform(-0.005, 0.005) for _ in range(2000)]

    def spread(min_cutoff_hz: float) -> float:
        f = _euro(min_cutoff_hz=min_cutoff_hz, beta=1.0)
        out = [f.update(0.5 + n, 0.5, i * DT_NS)[0] for i, n in enumerate(noise)]
        return statistics.pstdev(out[300:])

    assert spread(0.3) < spread(2.0)

    def steps_to_90(beta: float) -> int:
        f = _euro(min_cutoff_hz=0.5, beta=beta)
        for i in range(300):
            f.update(0.2, 0.2, i * DT_NS)
        for i in range(1, 400):
            if f.update(0.5, 0.2, (300 + i) * DT_NS)[0] >= 0.2 + 0.9 * 0.3:
                return i
        return 400

    assert steps_to_90(8.0) < steps_to_90(0.0)


# -- inside EyeInput.poll ---------------------------------------------------------------------


class _Source:
    """A tracker whose latest sample is set by hand."""

    def __init__(self) -> None:
        self.sample: GazeSample | None = None

    def latest(self) -> GazeSample | None:
        return self.sample


def _poll(eye: EyeInput, source: _Source, t_ns: int, x: float, valid: bool = True):
    source.sample = GazeSample(t_ns=t_ns, x=x, y=0.5, valid=valid)
    return eye.poll(t_ns)


def test_poll_filters_with_the_time_of_the_frame_and_resets_on_an_invalid_sample():
    source = _Source()
    eye = EyeInput(source, smoothing_config=SmoothingConfig(enabled=True, type="one_euro"))
    assert _poll(eye, source, 0, 0.2).x == 0.2
    moved = _poll(eye, source, DT_NS, 0.8)
    assert 0.2 < moved.x < 0.8
    frozen = _poll(eye, source, 2 * DT_NS, 0.0, valid=False)
    assert frozen.valid is False and frozen.x == moved.x  # frozen where it was
    assert _poll(eye, source, 3 * DT_NS, 0.9).x == 0.9  # a fresh start, not a blend with 0.2 / 0.8


def test_a1_best_with_ema_is_the_running_average_of_the_raw_gaze_as_before():
    """The default (`best` + `ema`) must give the same pointer as the plain running average over
    x / y / valid for any input stream (SPEC A1): replayed against GazeSmoother, which is unchanged."""
    rng = random.Random(11)
    source = _Source()
    eye = EyeInput(source, smoothing_config=SmoothingConfig(enabled=True, alpha=0.22))
    reference = GazeSmoother(SmoothingConfig(enabled=True, alpha=0.22))
    frozen = None
    for i in range(400):
        valid = rng.random() > 0.2
        x, y = rng.random(), rng.random()
        source.sample = GazeSample(t_ns=i, x=x, y=y, valid=valid)  # no pointer_* at all
        got = eye.poll(i)
        if valid:
            frozen = reference.update(x, y)
            assert (got.x, got.y, got.valid) == (*frozen, True)
        else:
            reference.reset()
            expected = frozen if frozen is not None else (0.5, 0.5)
            assert (got.x, got.y, got.valid) == (*expected, False)
