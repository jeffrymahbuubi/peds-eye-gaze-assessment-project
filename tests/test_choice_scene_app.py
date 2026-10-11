"""SPEC-scene-cause-effect-task.md step 4 through ``AssessmentApp`` (offscreen Qt): the canvas side of
A1 (a Choice-making run draws the scene), the run bar's prompt line (W2) and the idle-animation
setting reaching the run metadata (N3). The prompt WAVs make a trial last seconds of real time, so
the run is only looked at from its start."""

# The fixtures are imported from input_run_fixtures and then used by name.
# ruff: noqa: F811
from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.input_run_fixtures import make_app, parked, qapp, tick  # noqa: F401  (fixtures)

MOUSE_DWELL = {"pointer": "mouse", "selection": "dwell"}
TASK = "choice_making"


def test_a_choice_making_run_draws_the_scene_and_the_bar_names_the_prompt(make_app):
    app = make_app(TASK, choice=MOUSE_DWELL, client=None, trials=2)
    tick(app, 3)
    scene = app.canvas.scene
    assert scene["mode"] == "scene" and len(scene["buttons"]) == 8 and scene["idle_animation"] == "blinks"
    label = app.task.prompt_label
    assert label  # the prompt has started
    bar = app.view.run_bar
    assert bar.status_text() == f"Trial 1 of 2, Prompt: {label}, Mouse pointer"
    assert bar.prompt_label.text() == f"Prompt: {label}" and not bar.prompt_label.isHidden()
    image = app.canvas.grab().toImage()  # the whole scene mode paints in the run's own canvas
    assert not image.isNull() and app.canvas._scene_view.manifest is not None
    assert app.canvas._scene_view.manifest.source == "default"  # no scene file in the repository yet


def test_a_pause_drops_the_prompt_from_the_bar_and_resume_brings_it_back(make_app):
    app = make_app(TASK, choice=MOUSE_DWELL, client=None, trials=2)
    tick(app, 3)
    app._set_paused(True)
    assert app.view.run_bar.status_text() == "Paused, Trial 1 of 2"
    assert app.view.run_bar.prompt_label.isHidden()
    assert not app.canvas.grab().toImage().isNull()  # the canvas shows "Paused"
    app._set_paused(False)
    tick(app, 3)
    assert app.view.run_bar.status_text().startswith("Trial 1 of 2, Prompt: ")


def test_the_other_tests_have_no_prompt_line(make_app):
    app = make_app("click_static", choice=MOUSE_DWELL, client=None, trials=1)
    tick(app, 3)
    assert app.view.run_bar.prompt_label.isHidden() and "Prompt" not in app.view.run_bar.status_text()


def test_the_idle_animation_setting_reaches_the_canvas_and_metadata_json(make_app):
    for value in ("off", "blinks", "blinks_bob"):
        app = make_app(TASK, choice=MOUSE_DWELL, client=None, trials=1, structural={"idle_animation": value})
        tick(app, 2)
        assert app.canvas.scene["idle_animation"] == value
        assert app.canvas._scene_view.idle.mode == value
        assert app.metadata.settings["structural"]["idle_animation"] == value
        app.recorder.close()  # writes metadata.json
        written = json.loads((app.recorder.session_dir / "metadata.json").read_text(encoding="utf-8"))
        assert written["settings"]["structural"]["idle_animation"] == value
