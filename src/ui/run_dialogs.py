"""The run-end dialogs (SPEC-compass-task-flow.md 4C.6, 4C.8, U8, U14, HC7).

All are modal over the frozen canvas and follow ``docs/wireframes/run-end.md``:

* **Test Complete!**: Save / Save and View Report / Discard Results. Close or Esc = Save.
* **Discard these results?**: Discard / Keep. Keep is the default.
* **Quit the test?**: Quit test / Keep going. Keep going is the default.
* **Save the c completed trials?**: Save partial results / Discard results. Close or
  Esc = Save partial results. It is the second step of a confirmed quit, so Discard
  here has no confirmation of its own.
* **Nothing saved**: shown when a quit is confirmed before any trial finished; the
  empty run is discarded automatically.

The safe answer is always the default and always what Esc gives, so nothing
destructive happens by accident. :func:`ask_run_end` walks the dialogs for one
finished run and returns the action :func:`~src.engine.run_result.finish_run`
carries out; the dashboard (P8) calls the two in turn. Nothing here touches the disk
or a test.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..engine.run_result import DISCARD, SAVE, SAVE_AND_VIEW, RunResult
from .dialog_theme import apply_dialog_theme
from .wtmh_theme import DANGER

# A destructive answer: the theme has primary and ghost tiers only, so the dialogs
# add this one (scoped by object name, so no other page changes).
_DANGER_STYLE = f"""
QPushButton#runDlgDanger {{
    color: white;
    background: {DANGER};
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: 600;
}}
QPushButton#runDlgDanger:hover {{ background: #c94444; }}
QLabel#runDlgHeading {{ font-size: 20px; font-weight: 700; }}
"""

PRIMARY, GHOST, DANGER_TIER = "wtmhPrimary", "wtmhGhost", "runDlgDanger"


class _ChoiceDialog(QDialog):
    """A modal question with named answers.

    ``buttons`` are ``(key, label, tier)``; ``default`` is the key of the button
    Enter presses and ``on_close`` the key closing the window or pressing Esc gives.
    :attr:`choice` holds the key picked (``on_close`` until one is).
    """

    __test__ = False  # not a pytest class, whatever the name

    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        text: str,
        buttons: Sequence[tuple[str, str, str]],
        default: str,
        on_close: str,
        *,
        heading: bool = False,
    ) -> None:
        super().__init__(parent)
        apply_dialog_theme(self, _DANGER_STYLE)
        self.setWindowTitle(title)
        self.setModal(True)
        self.choice = on_close
        self._on_close = on_close

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(18)
        self.text_label = QLabel(text)
        self.text_label.setWordWrap(True)
        self.text_label.setMinimumWidth(360)
        if heading:
            self.text_label.setObjectName("runDlgHeading")
        layout.addWidget(self.text_label)

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch(1)
        self.buttons: dict[str, QPushButton] = {}
        for key, label, tier in buttons:
            button = QPushButton(label)
            button.setObjectName(tier)
            button.setProperty("choice", key)
            button.setAutoDefault(False)
            button.setDefault(key == default)
            button.clicked.connect(lambda _checked=False, k=key: self._pick(k))
            self.buttons[key] = button
            row.addWidget(button)
        layout.addLayout(row)
        if default in self.buttons:
            self.buttons[default].setFocus()

    def _pick(self, key: str) -> None:
        self.choice = key
        self.accept()

    def reject(self) -> None:
        """Close or Esc: the safe answer."""
        self.choice = self._on_close
        super().reject()

    def run(self) -> str:
        self.exec()
        return self.choice


class TestCompleteDialog(_ChoiceDialog):
    """"Test Complete!": ``choice`` is ``save``, ``save_and_view`` or ``discard``."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            "Test Complete",
            "Test Complete!",
            [
                (SAVE, "Save", GHOST),
                (SAVE_AND_VIEW, "Save and View Report", PRIMARY),
                (DISCARD, "Discard Results", DANGER_TIER),
            ],
            default=SAVE_AND_VIEW,
            on_close=SAVE,
            heading=True,
        )


class SavePartialDialog(_ChoiceDialog):
    """After a confirmed quit: ``choice`` is ``save`` or ``discard``."""

    def __init__(self, completed: int, parent: QWidget | None = None) -> None:
        noun = "trial" if completed == 1 else "trials"
        super().__init__(
            parent,
            "Save partial results",
            f"Save the {completed} completed {noun}?",
            [(SAVE, "Save partial results", PRIMARY), (DISCARD, "Discard results", DANGER_TIER)],
            default=SAVE,
            on_close=SAVE,
        )


def ask_choice(
    parent: QWidget | None,
    title: str,
    text: str,
    buttons: Sequence[tuple[str, str, str]],
    default: str,
    on_close: str,
) -> str:
    """A modal question with named answers, for the dashboard's own confirmations (the
    Test List's Delete Test, the configuration page's save questions). ``buttons`` are
    ``(key, label, tier)`` with the tiers above; returns the key picked, ``on_close``
    for Esc or the window's close button."""
    return _ChoiceDialog(parent, title, text, buttons, default, on_close).run()


def ask_test_complete(parent: QWidget | None = None) -> str:
    """Show "Test Complete!"; returns ``save``, ``save_and_view`` or ``discard``."""
    return TestCompleteDialog(parent).run()


def ask_save_partial(parent: QWidget | None, completed: int) -> str:
    """Show the Save-partial question; returns ``save`` or ``discard``."""
    return SavePartialDialog(completed, parent).run()


def confirm_discard(parent: QWidget | None = None) -> bool:
    """"Discard these results?": True only if Discard was chosen."""
    dialog = _ChoiceDialog(
        parent,
        "Discard results",
        "Discard these results? This cannot be undone.",
        [("discard", "Discard", DANGER_TIER), ("keep", "Keep", PRIMARY)],
        default="keep",
        on_close="keep",
    )
    return dialog.run() == "discard"


def confirm_quit(parent: QWidget | None, completed: int, planned: int) -> bool:
    """"Quit the test?": True only if Quit test was chosen. Keep going is the default."""
    dialog = _ChoiceDialog(
        parent,
        "Quit the test?",
        f"Quit the test? {completed} of {planned} trials are done.",
        [("quit", "Quit test", DANGER_TIER), ("keep", "Keep going", PRIMARY)],
        default="keep",
        on_close="keep",
    )
    return dialog.run() == "quit"


def show_nothing_saved(parent: QWidget | None = None) -> None:
    """Tell the operator a quit before the first trial saved nothing."""
    _ChoiceDialog(
        parent,
        "Nothing saved",
        "No trials were completed, so nothing was saved.",
        [("ok", "OK", PRIMARY)],
        default="ok",
        on_close="ok",
    ).run()


def ask_run_end(
    result: RunResult,
    parent: QWidget | None = None,
    *,
    complete: Callable[[QWidget | None], str] = ask_test_complete,
    partial: Callable[[QWidget | None, int], str] = ask_save_partial,
    confirm: Callable[[QWidget | None], bool] = confirm_discard,
    nothing: Callable[[QWidget | None], None] = show_nothing_saved,
) -> str:
    """Walk the dialogs for one finished, recorded run; returns ``save``,
    ``save_and_view`` or ``discard`` for :func:`~src.engine.run_result.finish_run`.

    * no trial finished: say so and discard (no choice is offered);
    * the run completed: Test Complete!; Discard Results asks once more, and Keep
      brings Test Complete! back;
    * the run was ended early with trials done: Save partial / Discard, no extra
      confirmation.

    The dialogs are parameters so a test can answer them without a modal loop.
    """
    if result.is_empty:
        nothing(parent)
        return DISCARD
    if result.is_complete:
        while True:
            choice = complete(parent)
            if choice != DISCARD or confirm(parent):
                return choice
    return DISCARD if partial(parent, result.completed) == DISCARD else SAVE
