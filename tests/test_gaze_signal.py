"""The cursor's gaze signal: BPOG / APOG, and the retired FPOG (SPEC-gaze-stability-and-positioning.md
4.1, 4.9, acceptance A2, A4, A12, A13) from the REC record to the pointer, with the recorded raw
gaze untouched. FPOG ("Fixation") is no longer offered by any setting; its internal path stays
tested here because a dwell must survive the same gaps for APOG."""

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
    app_smoothing_on,
    apply_gaze_signal,
    clamp_aac_filter,
    normalize_signal,
    normalize_smoothing_type,
    pointer_from_rec,
    retired_signal_note,
    signal_label,
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
    assert normalize_signal(SIGNAL_FIXATION) == SIGNAL_BEST  # A12: the retired one is App smoothing
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


# -- A12: the retired Fixation, A13: Assistive is never smoothed by the app ----------------------


def test_a12_the_signals_are_named_as_the_two_approaches_and_the_retired_one_keeps_its_name():
    assert signal_label(SIGNAL_BEST) == "App smoothing (raw gaze)"
    assert signal_label(SIGNAL_ASSISTIVE) == "Gazepoint Assistive (APOG)"
    assert signal_label(SIGNAL_FIXATION) == "Fixation (FPOG), no longer offered"
    assert signal_label("bogus") == "App smoothing (raw gaze)"


def test_a12_a_retired_signal_has_a_session_log_note_and_nothing_else_does():
    assert retired_signal_note("fixation") == (
        "Gaze signal 'fixation' is no longer offered; using App smoothing (raw gaze)."
    )
    assert all(retired_signal_note(v) is None for v in (SIGNAL_BEST, SIGNAL_ASSISTIVE, "bogus", None))


@pytest.mark.parametrize("signal", [SIGNAL_BEST, SIGNAL_ASSISTIVE])
def test_a13_the_app_never_smooths_assistive_whatever_the_setting_says(signal):
    assert app_smoothing_on(signal, True) is (signal == SIGNAL_BEST)
    assert app_smoothing_on(signal, False) is False


def test_a13_a_retired_signal_smooths_as_app_smoothing_does():
    assert app_smoothing_on(SIGNAL_FIXATION, True) is True and app_smoothing_on(SIGNAL_FIXATION, False) is False


def _pointer_track(signal: str, smoothing_enabled: bool) -> list[tuple[float, float]]:
    """The pointer for APOG samples that jump from (0.2, 0.2) to (0.8, 0.8), through the same
    EyeInput a run builds (smoothing as ``app_smoothing_on`` decides)."""
    source = _Source()
    config = SmoothingConfig(enabled=app_smoothing_on(signal, smoothing_enabled), alpha=0.1)
    eye = EyeInput(source, smoothing_config=config)
    track = []
    for i, (x, y) in enumerate([(0.2, 0.2)] * 3 + [(0.8, 0.8)] * 3):
        rec = f'<REC BPOGX="{x}" BPOGY="{y}" BPOGV="1" APOGX="{x}" APOGY="{y}" APOGV="1" />'
        source.sample = rec_to_sample(parse_rec(rec), 1000 + i * 10_000_000, signal)
        p = eye.poll(1000 + i * 10_000_000)
        track.append((p.x, p.y))
    return track


def test_a13_with_assistive_the_pointer_is_the_same_with_the_app_smoothing_on_or_off():
    on, off = _pointer_track(SIGNAL_ASSISTIVE, True), _pointer_track(SIGNAL_ASSISTIVE, False)
    assert on == off
    assert on[3] == (0.8, 0.8)  # a jump lands at once: nothing lags behind Gazepoint's own average


def test_a13_with_app_smoothing_the_setting_still_makes_the_pointer_lag():
    smoothed, raw = _pointer_track(SIGNAL_BEST, True), _pointer_track(SIGNAL_BEST, False)
    assert raw[3] == (0.8, 0.8)
    assert 0.2 < smoothed[3][0] < 0.5  # alpha 0.1: far from landed one frame after the jump


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


def test_an_app_smoothing_run_start_sets_the_signal_and_never_touches_aac_filter():
    tracker = _Tracker()
    assert apply_gaze_signal(tracker, SIGNAL_BEST, 30) == ["Gaze signal: App smoothing (raw gaze)."]
    assert (tracker.signal, tracker.aac) == (SIGNAL_BEST, [])


def test_a12_a_retired_signal_run_start_notes_it_first_and_runs_on_app_smoothing():
    tracker = _Tracker()
    lines = apply_gaze_signal(tracker, normalize_signal("fixation"), 30, "fixation")
    assert lines == [
        "Gaze signal 'fixation' is no longer offered; using App smoothing (raw gaze).",
        "Gaze signal: App smoothing (raw gaze).",
    ]
    assert (tracker.signal, tracker.aac) == (SIGNAL_BEST, [])
    # The note is about the config, so a source with no signal methods still carries it.
    assert apply_gaze_signal(object(), SIGNAL_BEST, 15, "fixation") == [lines[0]]


def test_an_assistive_run_start_sends_the_filter_length_and_logs_it():
    tracker = _Tracker()
    lines = apply_gaze_signal(tracker, SIGNAL_ASSISTIVE, 30)
    assert (tracker.signal, tracker.aac) == (SIGNAL_ASSISTIVE, [30])
    assert lines == ["Gaze signal: Gazepoint Assistive (APOG).", "AAC filter set to 30 samples."]
    assert apply_gaze_signal(_Tracker(), SIGNAL_ASSISTIVE, 500)[1] == "AAC filter set to 60 samples."


def test_an_unsent_filter_is_a_warning_line_and_a_source_without_the_methods_is_left_alone():
    lines = apply_gaze_signal(_Tracker(sends=False), SIGNAL_ASSISTIVE, 15)
    assert lines[1].startswith("WARNING: could not send AAC_FILTER 15")
    assert apply_gaze_signal(object(), SIGNAL_ASSISTIVE, 15) == []  # a mouse stand-in, a NoTracker
