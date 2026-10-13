"""The cursor's gaze signal: BPOG / FPOG / APOG (SPEC-gaze-stability-and-positioning.md 4.1,
acceptance A2, A4) from the REC record to the pointer, with the recorded raw gaze untouched."""

from __future__ import annotations

import pytest

from src.data.schema import GazeSample
from src.inputs.base import Pointer
from src.inputs.eye_input import DwellConfig, DwellSelector, EyeInput, SmoothingConfig
from src.inputs.gaze_signal import (
    AAC_FILTER_DEFAULT,
    SIGNAL_ASSISTIVE,
    SIGNAL_BEST,
    SIGNAL_FIXATION,
    apply_gaze_signal,
    clamp_aac_filter,
    normalize_signal,
    normalize_smoothing_type,
    pointer_from_rec,
)
from src.inputs.gazepoint_client import parse_rec, rec_to_sample
from src.tasks.base_task import BaseTask, TargetSpec

# Three different places, so which one drives what is unambiguous.
REC = (
    '<REC BPOGX="0.10" BPOGY="0.20" BPOGV="1" FPOGX="0.30" FPOGY="0.40" FPOGV="1" FPOGID="7" '
    'FPOGD="0.25" APOGX="0.50" APOGY="0.60" APOGV="1" LPMM="3.1" RPMM="3.2" />'
)


def _sample(rec: str = REC, signal: str = SIGNAL_BEST) -> GazeSample:
    return rec_to_sample(parse_rec(rec), 1000, signal)


# -- A2: the signal behind the pointer, the raw gaze unchanged ---------------------------------


@pytest.mark.parametrize(
    ("signal", "expected"),
    [(SIGNAL_BEST, (0.10, 0.20)), (SIGNAL_FIXATION, (0.30, 0.40)), (SIGNAL_ASSISTIVE, (0.50, 0.60))],
)
def test_the_pointer_follows_the_chosen_signal_and_the_raw_gaze_stays_bpog(signal, expected):
    s = _sample(signal=signal)
    assert (s.pointer_x, s.pointer_y, s.pointer_valid) == (*expected, True)
    # What is recorded as the raw gaze is BPOG whatever drives the cursor.
    assert (s.x, s.y, s.valid) == (0.10, 0.20, True)
    assert (s.fixation_id, s.fix_duration_s) == (7, 0.25)


def test_the_default_signal_is_the_raw_gaze_exactly():
    s = rec_to_sample(parse_rec(REC), 5)  # no signal given: today's call
    assert (s.pointer_x, s.pointer_y, s.pointer_valid) == (s.x, s.y, s.valid)


def test_best_falls_back_to_fpog_like_the_raw_gaze_does():
    s = _sample(REC.replace('BPOGV="1"', 'BPOGV="0"'))
    assert (s.x, s.y, s.valid) == (0.30, 0.40, True)
    assert (s.pointer_x, s.pointer_y, s.pointer_valid) == (0.30, 0.40, True)


def test_fixation_is_invalid_when_fpogv_is_zero_though_the_raw_gaze_is_valid():
    s = _sample(REC.replace('FPOGV="1"', 'FPOGV="0"'), SIGNAL_FIXATION)
    assert s.pointer_valid is False
    assert s.valid is True and (s.x, s.y) == (0.10, 0.20)  # BPOG is still fine


def test_assistive_is_invalid_without_an_apog_record_or_when_apogv_is_zero():
    no_apog = _sample(REC.split(" APOGX")[0] + " />", SIGNAL_ASSISTIVE)
    assert (no_apog.pointer_valid, no_apog.pointer_x, no_apog.pointer_y) == (False, 0.0, 0.0)
    assert _sample(REC.replace('APOGV="1"', 'APOGV="0"'), SIGNAL_ASSISTIVE).pointer_valid is False


def test_pointer_from_rec_gives_zero_for_a_missing_coordinate_and_never_valid():
    assert pointer_from_rec({"FPOGV": "1"}, SIGNAL_FIXATION, (None, None, False)) == (0.0, 0.0, False)


def test_unknown_values_fall_back_to_the_defaults():
    assert normalize_signal("bogus") == SIGNAL_BEST and normalize_signal(None) == SIGNAL_BEST
    assert normalize_smoothing_type("bogus") == "ema" and normalize_smoothing_type("one_euro") == "one_euro"
    assert (clamp_aac_filter(0), clamp_aac_filter(99), clamp_aac_filter("x")) == (1, 60, AAC_FILTER_DEFAULT)


class _Source:
    def __init__(self, sample: GazeSample | None = None) -> None:
        self.sample = sample

    def latest(self) -> GazeSample | None:
        return self.sample


def test_eye_input_drives_the_pointer_from_the_signal_and_records_the_raw_sample():
    source = _Source(_sample(signal=SIGNAL_FIXATION))
    eye = EyeInput(source, smoothing_config=SmoothingConfig(enabled=False))
    pointer = eye.poll(0)
    assert (pointer.x, pointer.y, pointer.valid) == (0.30, 0.40, True)
    recorded = eye.latest_sample()
    assert (recorded.x, recorded.y) == (0.10, 0.20)  # BPOG: what the recorder gets


def test_an_invalid_signal_freezes_the_pointer_even_though_the_raw_gaze_is_valid():
    source = _Source(_sample(signal=SIGNAL_FIXATION))
    eye = EyeInput(source, smoothing_config=SmoothingConfig(enabled=False))
    eye.poll(0)
    source.sample = _sample(REC.replace('FPOGV="1"', 'FPOGV="0"').replace('FPOGX="0.30"', 'FPOGX="0.9"'), SIGNAL_FIXATION)
    frozen = eye.poll(1)
    assert (frozen.x, frozen.y, frozen.valid) == (0.30, 0.40, False)


# -- A4: a fixation dwell survives the microsaccade gaps ------------------------------------------


class _OneTarget(BaseTask):
    def __init__(self, config, w, h, dwell):
        self._target = TargetSpec(index=0, x_norm=0.5, y_norm=0.5, radius_px=60.0)
        super().__init__(config, w, h, dwell=dwell)

    def build_targets(self):
        return [self._target]


class _FpogStream:
    """150 Hz RECs resting on the target, FPOGV dropping to 0 for ``gap_ms`` every ``period_ms``
    (a microsaccade); BPOG stays valid, as it does on the device."""

    def __init__(self, gap_ms: float, period_ms: float = 250.0) -> None:
        self.gap_ms, self.period_ms = gap_ms, period_ms
        self.t_ns = 0

    def latest(self) -> GazeSample:
        in_gap = (self.t_ns / 1e6) % self.period_ms >= self.period_ms - self.gap_ms
        rec = (
            f'<REC BPOGX="0.5" BPOGY="0.5" BPOGV="1" FPOGX="0.5" FPOGY="0.5" '
            f'FPOGV="{0 if in_gap else 1}" />'
        )
        return rec_to_sample(parse_rec(rec), self.t_ns, SIGNAL_FIXATION)


def _dwell_hits(gap_ms: float, seconds: float = 2.0) -> bool:
    dwell = DwellSelector(DwellConfig(threshold_ms=700.0, refractory_ms=500.0, hold_grace_ms=120.0))
    task = _OneTarget({}, 1000, 800, dwell)
    stream = _FpogStream(gap_ms)
    eye = EyeInput(stream, dwell_config=dwell.config, smoothing_config=SmoothingConfig(enabled=False))
    step = round(1e9 / 150)
    for i in range(round(seconds * 150)):
        stream.t_ns = i * step
        pointer = eye.poll(stream.t_ns)
        task.update(stream.t_ns, Pointer(pointer.x, pointer.y, pointer.valid, False))
        if task.trials and task.trials[-1].is_hit:
            return True
    return False


def test_a4_a_dwell_completes_through_gaps_shorter_than_the_hold_grace():
    assert _dwell_hits(gap_ms=80.0) is True


def test_a4_a_gap_longer_than_the_hold_grace_resets_the_dwell():
    # The same stream with 200 ms gaps never keeps 700 ms of dwell: the grace is what bridges.
    assert _dwell_hits(gap_ms=200.0) is False


# -- apply_gaze_signal: what a run start does to the tracker -----------------------------------------


class _Tracker:
    def __init__(self, sends: bool = True) -> None:
        self.signal = None
        self.aac: list[int] = []
        self._sends = sends

    def set_pointer_signal(self, signal: str) -> None:
        self.signal = signal

    def set_aac_filter(self, samples: int) -> bool:
        self.aac.append(samples)
        return self._sends


def test_a_non_assistive_run_start_sets_the_signal_and_never_touches_aac_filter():
    for signal in (SIGNAL_BEST, SIGNAL_FIXATION):
        tracker = _Tracker()
        assert apply_gaze_signal(tracker, signal, 30) == [
            f"Gaze signal: {'Raw gaze (BPOG)' if signal == SIGNAL_BEST else 'Fixation (FPOG)'}."
        ]
        assert (tracker.signal, tracker.aac) == (signal, [])


def test_an_assistive_run_start_sends_the_filter_length_and_logs_it():
    tracker = _Tracker()
    lines = apply_gaze_signal(tracker, SIGNAL_ASSISTIVE, 30)
    assert (tracker.signal, tracker.aac) == (SIGNAL_ASSISTIVE, [30])
    assert lines == ["Gaze signal: Assistive (APOG).", "AAC filter set to 30 samples."]
    assert apply_gaze_signal(_Tracker(), SIGNAL_ASSISTIVE, 500)[1] == "AAC filter set to 60 samples."


def test_an_unsent_filter_is_a_warning_line_and_a_source_without_the_methods_is_left_alone():
    lines = apply_gaze_signal(_Tracker(sends=False), SIGNAL_ASSISTIVE, 15)
    assert lines[1].startswith("WARNING: could not send AAC_FILTER 15")
    assert apply_gaze_signal(object(), SIGNAL_ASSISTIVE, 15) == []  # a mouse stand-in, a NoTracker
