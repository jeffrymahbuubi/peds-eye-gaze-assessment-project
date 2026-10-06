"""Full-page task configuration (SPEC-compass-task-flow.md 4B.1-4B.5).

Replaces the modal :class:`~src.ui.task_settings_dialog.TaskSettingsDialog` inside
the dashboard: titled cards in three columns on one scrolling page
(:class:`~src.ui.config_form.ConfigForm` builds them from the registries' layout
spec -- one control per setting that applies to the task, none hidden), with
Preview Test / Save & Continue / Cancel pinned underneath. The page only **emits
signals**: it never writes a file or touches a test. The dashboard (P8) applies the
4B.4 save rules (forced rename, Update / Save under a new name, the profile file) and
launches Preview from the unsaved values this page hands over.

Values are plain data. ``collect_values()`` is ``{"live", "structural"}``, the two
dicts a recorded run gets as ``live_overrides`` / ``structural_overrides`` (``live``
flat by dotted key, ``structural`` nested like ``TaskSettingsDialog.overrides()``).
``collect_entry()`` adds the Test Name, Configuration Name and Notes and is what
``saveRequested`` carries.

Standard is the task's computed defaults, never stored (4B.4). The page remembers the
configuration it last loaded (Standard, a saved name, or a test's own snapshot):
"Modified from ..." and the ask-before-replacing rule compare against it. The page is
*dirty* when anything differs from the last ``load_values()`` / ``mark_clean()``;
Cancel then asks first.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..engine.settings_profile import STANDARD_CONFIG_NAME, NamedConfig, validate_config_name
from ..engine.subject_test_record import validate_test_name
from ..engine.target_size import screen_scale, viewing_distance_mm
from ..engine.task_info import TASK_INFO
from .config_form import ConfigForm
from .config_widgets import ask_two_choice, estimated_canvas_px
from .settings_registry import get_nested, set_nested
from .settings_snapshot import complete_settings, settings_snapshot


class TaskConfigPage(QWidget):
    """The configuration page of one task (a page is per task: controls that do
    not apply to it are simply absent)."""

    saveRequested = Signal(dict)  # collect_entry(); only while Save & Continue is enabled
    cancelRequested = Signal()  # nothing to discard, or the discard was confirmed
    previewRequested = Signal(dict)  # collect_values(): the unsaved form, always allowed

    def __init__(
        self, task_id: str, config: dict[str, Any], *, screen: Any = None, parent: QWidget | None = None
    ) -> None:
        """``config`` is the task's merged run config (``load_task_config``); its values
        are the Standard defaults. ``screen`` (a QScreen, duck-typed) sizes the px
        figures and the shrink hints; the default is this page's own screen."""
        super().__init__(parent)
        self.task_id = task_id
        self._config = config
        self._loading = True  # no change handling until the form is built
        app_cfg = config.get("app", {})
        screen = screen if screen is not None else self.screen()
        self._task_name = TASK_INFO.get(task_id, (task_id, ""))[0]
        self._standard = settings_snapshot(task_id, config)
        self._form = ConfigForm(
            task_id,
            self._standard,
            config,
            screen_scale(screen, app_cfg),
            viewing_distance_mm(app_cfg),
            estimated_canvas_px(screen, app_cfg),
        )
        self._subject_id = ""
        self._existing_names: list[str] = []
        self._own_name = ""
        self._named: dict[str, NamedConfig] = {}
        self._note = ""
        # The Configuration Name box's text now and before its last change, and whether
        # that change happened in this very event: a pick from the list changes the text
        # and emits ``activated`` in one go, typing and then Enter does not.
        self._config_text = self._prev_config_text = STANDARD_CONFIG_NAME
        self._text_just_changed = False

        self._build_ui()
        self._standard_flat = self._values()  # as the controls show it (read back: clamped)
        self._loaded_name = STANDARD_CONFIG_NAME
        self._loaded_values = dict(self._standard_flat)
        self._loading = False
        self._refresh()
        self._baseline = self._state()

    # The form's widgets, under the names tests and the dashboard use.
    @property
    def cards(self) -> dict[str, QFrame]:
        return self._form.cards

    @property
    def fit_hint(self) -> QFrame | None:
        return self._form.fit_hint

    @property
    def fit_hint_label(self) -> QLabel | None:
        return self._form.fit_hint_label

    # -- public API -----------------------------------------------------------

    def set_context(
        self,
        *,
        subject_id: str | None = None,
        existing_test_names: Iterable[str] | None = None,
        named_configs: Iterable[NamedConfig] | None = None,
    ) -> None:
        """What the page needs from outside (``None`` leaves a part as it was): the
        subject (shown in the header), the subject's test names (a Test Name must be
        unique among them, the test's own name aside) and their saved configurations
        (the Configuration Name list: Standard first, then these, newest first)."""
        if subject_id is not None:
            self._subject_id = subject_id.strip()
            self.subtitle_label.setText(self._subtitle())
        if existing_test_names is not None:
            self._existing_names = list(existing_test_names)
        if named_configs is not None:
            self._set_named(list(named_configs))
        self._refresh()

    def load_values(
        self,
        *,
        test_name: str | None = None,
        notes: str | None = None,
        config_name: str | None = None,
        live: dict[str, Any] | None = None,
        structural: dict[str, Any] | None = None,
    ) -> None:
        """Fill the form, then take it as the clean baseline. A key ``live`` /
        ``structural`` lacks gets its Standard default and an unknown key is ignored
        (4B.4); ``None`` for the name or notes leaves that field alone. The dashboard
        calls this when it opens the page, never on show (4B.6: Preview returns to the
        form exactly as it was)."""
        values = complete_settings(self.task_id, self._config, live, structural)
        self._loading = True
        try:
            if test_name is not None:
                self._form.test_name_edit.setText(test_name)
                self._own_name = test_name.strip()
                self.title_label.setText(f"{self._own_name or self._task_name} Configuration")
            if notes is not None:
                self._form.notes_edit.setPlainText(notes)
            self._apply(values)
            name = (config_name or "").strip()
            if not name or name.casefold() == STANDARD_CONFIG_NAME.casefold():
                name = STANDARD_CONFIG_NAME
            self._set_config_text(name)
            self._loaded_name = name
            self._loaded_values = self._values()
        finally:
            self._loading = False
        self._note = ""
        self._refresh()
        self.mark_clean()

    def collect_values(self) -> dict[str, dict[str, Any]]:
        """``{"live": {...}, "structural": {...}}`` of the form as it is now: every
        setting of the task, nothing written (Preview and Save both start here)."""
        return self._split(self._values())

    def collect_entry(self) -> dict[str, Any]:
        """What ``saveRequested`` carries: :meth:`collect_values` plus the Test Name,
        the Configuration Name (as typed, trimmed) and the Notes."""
        return {
            "test_name": self._form.test_name_edit.text().strip(),
            "config_name": self._form.config_combo.currentText().strip(),
            "notes": self._form.notes_edit.toPlainText(),
            **self.collect_values(),
        }

    def standard_values(self) -> dict[str, dict[str, Any]]:
        """The task's defaults in :meth:`collect_values` shape: what Standard means (the
        dashboard compares against it for the forced rename of 4B.4)."""
        return self._split(self._standard_flat)

    def loaded_config_name(self) -> str:
        return self._loaded_name

    def is_modified(self) -> bool:
        """Do the option values differ from the configuration last loaded?"""
        return self._values() != self._loaded_values

    def is_dirty(self) -> bool:
        """Is anything (name, notes, configuration name, a value) different from the
        last ``load_values()`` / ``mark_clean()``?"""
        return self._state() != self._baseline

    def mark_clean(self) -> None:
        self._baseline = self._state()

    def save_problem(self) -> str | None:
        """Why Save & Continue is disabled, or ``None`` (4B.3). Standard with changed
        values is not a problem here: the dashboard asks for a new name at save time
        (4B.4, AB8)."""
        error = validate_test_name(
            self._form.test_name_edit.text(), self._existing_names, exclude=self._own_name or None
        )
        if error:
            return error
        name = self._form.config_combo.currentText().strip()
        if name.casefold() == STANDARD_CONFIG_NAME.casefold():
            return None
        return validate_config_name(name)

    def show_note(self, text: str) -> None:
        """A muted line in the footer until the next edit (e.g. "Preview finished.
        Nothing was recorded.", 4B.6)."""
        self._note = text
        self._refresh_footer()

    # -- building ---------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(16)

        header = QVBoxLayout()
        header.setSpacing(2)
        self.title_label = QLabel(f"{self._task_name} Configuration")
        self.title_label.setObjectName("wtmhPageTitle")
        self.subtitle_label = QLabel(self._subtitle())
        self.subtitle_label.setObjectName("wtmhMuted")
        header.addWidget(self.title_label)
        header.addWidget(self.subtitle_label)
        outer.addLayout(header)

        # The cards scroll above a pinned footer (SPEC-ui-setup-task-selection.md S22.3),
        # so a smaller window or 125/150 % scaling scrolls instead of clipping and
        # Save & Continue stays reachable.
        scroll = QScrollArea()
        scroll.setObjectName("wtmhConfigScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        content = self._form.build()
        scroll.setWidget(content)
        # setWidget() turns autoFillBackground on for the viewport and the content
        # widget (black bands between the cards); the QSS rule reaches only the
        # viewport, so both are cleared here (S22.5).
        scroll.viewport().setAutoFillBackground(False)
        content.setAutoFillBackground(False)
        self.scroll_area = scroll
        outer.addWidget(scroll, stretch=1)

        footer = QHBoxLayout()
        footer.setSpacing(10)
        self.preview_button = self._button("Preview Test", "cfgPreview")
        self.save_button = self._button("Save && Continue", "cfgSave")
        self.cancel_button = self._button("Cancel", "cfgCancel")
        self.footer_message = QLabel("")
        self.footer_message.setObjectName("wtmhMuted")
        self.footer_message.setWordWrap(True)
        for widget in (self.preview_button, self.save_button, self.cancel_button):
            footer.addWidget(widget)
        footer.addSpacing(6)
        footer.addWidget(self.footer_message, stretch=1)
        outer.addLayout(footer)
        self._connect()

    @staticmethod
    def _button(text: str, name: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(name)  # styled by the theme's cfg* aliases of the button tiers
        button.setAutoDefault(False)  # Enter never saves (4B.5)
        return button

    def _connect(self) -> None:
        form = self._form
        for control in form.controls.values():
            signal = control.toggled if isinstance(control, QCheckBox) else control.valueChanged
            signal.connect(self._on_changed)
        form.test_name_edit.textChanged.connect(self._on_changed)
        form.notes_edit.textChanged.connect(self._on_changed)
        form.config_combo.editTextChanged.connect(self._on_config_text)
        form.config_combo.activated.connect(self._on_config_activated)
        form.reset_button.clicked.connect(self._on_reset)
        self.preview_button.clicked.connect(lambda: self.previewRequested.emit(self.collect_values()))
        self.save_button.clicked.connect(self._on_save)
        self.cancel_button.clicked.connect(self._on_cancel)

    def _subtitle(self) -> str:
        return f"{self._task_name} · Subject {self._subject_id}" if self._subject_id else self._task_name

    # -- reading and writing the form ----------------------------------------------

    def _values(self) -> dict[str, Any]:
        """Every option's current value, flat by registry key."""
        out: dict[str, Any] = {}
        for key, control in self._form.controls.items():
            kind = self._form.kinds[key]
            if kind == "bool":
                out[key] = control.isChecked()
            elif kind == "choice":
                out[key] = str(control.value())
            elif kind == "int":
                out[key] = int(control.value())
            else:
                out[key] = float(control.value())
        return out

    def _split(self, flat: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """A flat ``{key: value}`` as ``{"live": flat, "structural": nested}``."""
        live: dict[str, Any] = {}
        structural: dict[str, Any] = {}
        for key, value in flat.items():
            if self._form.layers[key] == "live":
                live[key] = value
            else:
                set_nested(structural, key, value)
        return {"live": live, "structural": structural}

    def _state(self) -> tuple:
        form = self._form
        return (
            form.test_name_edit.text(),
            form.notes_edit.toPlainText(),
            form.config_combo.currentText().strip(),
            self._values(),
        )

    def _apply(self, snapshot: dict[str, dict[str, Any]]) -> None:
        """Put a ``{"live", "structural"}`` snapshot into the controls. A value a control
        cannot take (a hand-edited file) shows the Standard default instead."""
        for key, control in self._form.controls.items():
            if self._form.layers[key] == "live":
                value = snapshot["live"].get(key)
            else:
                value = get_nested(snapshot["structural"], key)
            default = self._standard_flat[key]
            kind = self._form.kinds[key]
            if kind == "bool":
                control.setChecked(value if isinstance(value, bool) else default)
            elif kind == "choice":
                control.setValue(value if value in control.buttons() else default)
            else:
                is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
                control.setValue(value if is_number else default)

    # -- change handling --------------------------------------------------------------

    def _on_changed(self, *_args: object) -> None:
        if self._loading:
            return
        self._note = ""
        self._refresh()

    def _refresh(self) -> None:
        form = self._form
        for master, widgets in form.dependents:  # greyed in place, never hidden (4B.3)
            enabled = bool(form.controls[master].isChecked())
            for widget in widgets:
                widget.setEnabled(enabled)
        form.update_hint(self._values())
        modified = self.is_modified()
        form.modified_label.setText(f'Modified from "{self._loaded_name}"' if modified else "")
        form.modified_label.setVisible(modified)
        self._refresh_footer()

    def _refresh_footer(self) -> None:
        problem = self.save_problem()
        self.save_button.setEnabled(problem is None)
        self.footer_message.setText(problem or self._note)

    # -- configuration names -------------------------------------------------------------

    def _set_named(self, configs: list[NamedConfig]) -> None:
        self._named = {config.name.casefold(): config for config in configs}
        combo = self._form.config_combo
        text = combo.currentText()
        was_loading, self._loading = self._loading, True
        try:
            combo.clear()
            combo.addItem(STANDARD_CONFIG_NAME)
            for config in configs:
                combo.addItem(config.name)
        finally:
            self._loading = was_loading
        self._set_config_text(text)

    def _set_config_text(self, text: str) -> None:
        """Show ``text`` in the Configuration Name box without a change event."""
        combo = self._form.config_combo
        was_loading, self._loading = self._loading, True
        try:
            index = combo.findText(text, Qt.MatchFlag.MatchFixedString)
            if index >= 0:
                combo.setCurrentIndex(index)
            combo.setEditText(text)
        finally:
            self._loading = was_loading
        self._config_text = self._prev_config_text = text

    def _on_config_text(self, text: str) -> None:
        if self._loading:
            return
        self._prev_config_text, self._config_text = self._config_text, text
        self._text_just_changed = True
        QTimer.singleShot(0, self._text_settled)
        self._on_changed()

    def _text_settled(self) -> None:
        self._text_just_changed = False

    def _snapshot_for_name(self, name: str) -> dict[str, dict[str, Any]] | None:
        if name.strip().casefold() == STANDARD_CONFIG_NAME.casefold():
            return self._standard
        config = self._named.get(name.strip().casefold())
        if config is None:
            return None
        return complete_settings(self.task_id, self._config, config.live, config.structural)

    def _load_configuration(self, name: str, snapshot: dict[str, dict[str, Any]]) -> None:
        self._loading = True
        try:
            self._apply(snapshot)
            self._set_config_text(name)
            self._loaded_name = name
            self._loaded_values = self._values()
        finally:
            self._loading = False
        self._note = ""
        self._refresh()

    def _on_config_activated(self, index: int) -> None:
        """The operator picked a name from the list: load all its values (4B.4 / 2), after
        asking if that would replace edits. Typing a new name never loads."""
        name = self._form.config_combo.itemText(index)
        snapshot = self._snapshot_for_name(name)
        if snapshot is None:
            return
        if self.is_modified() and not self._ask(
            "Load configuration", f"Replace your edits with configuration '{name}'?",
            "Replace", "Keep my edits",
        ):
            # Back to what the box showed before this pick (a pick changes the text in the
            # same event as ``activated``; an Enter after typing a name has nothing to undo).
            self._set_config_text(self._prev_config_text if self._text_just_changed else name)
            return
        self._load_configuration(name, snapshot)

    def _on_reset(self) -> None:
        """Standard with every value at its default; Test Name and Notes stay (4B.4 / 5).
        Unsaved until Save & Continue."""
        self._load_configuration(STANDARD_CONFIG_NAME, self._standard)

    # -- footer actions ---------------------------------------------------------------------

    def _on_save(self) -> None:
        if self.save_problem() is None:
            self.saveRequested.emit(self.collect_entry())

    def _on_cancel(self) -> None:
        """No edits: back at once. Edits: ask first (4B.5). Writes nothing either way."""
        if self.is_dirty() and not self._ask(
            "Discard changes", "Discard your changes?", "Discard", "Keep editing", default_accept=False
        ):
            return
        self.cancelRequested.emit()

    def _ask(
        self, title: str, text: str, accept: str, reject: str, *, default_accept: bool = True
    ) -> bool:
        """The page's modal question (a method so a test can answer it)."""
        return ask_two_choice(self, title, text, accept, reject, default_accept=default_accept)
