"""The report's Target Map widget (SPEC-compass-task-flow.md 4D.7).

A custom widget painting with :class:`QPainter` from the report dict: no
per-sample graphics items. The drawing itself is :mod:`target_map_paint`; this class
keeps the model, the overlay switches (Targets / Scanpath / Heat map) and the
selected trial, centres the canvas rectangle at its true aspect in whatever room it
has, and renders to an image for the PDF.

Two uses: the Summary's map (the whole test; :meth:`set_fit_to_width` makes its height
follow its width) and the Detailed view's pane (one trial, :meth:`set_trial`).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QRectF, QSize
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from .target_map_paint import MapModel, build_model, paint_map

MARGIN = 2  # px around the canvas rectangle, so its border is not clipped


class TargetMapWidget(QWidget):
    """Marks, fixation scanpaths and heat map of one test on the canvas's own aspect.

    The overlays are ``targets`` (the marks and the faint layout, default on),
    ``path`` (each trial's fixation scanpath) and ``heat`` (default off); they apply to the
    whole-test view. After :meth:`set_trial` the widget shows that one trial (its target, its
    smoothed gaze path, its numbered fixations) and the overlays do not matter.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = MapModel()
        self._overlays = {"targets": True, "path": False, "heat": False}
        self._trial: int | None = None
        self._fit_to_width = False
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(160, 90)

    # -- data ---------------------------------------------------------------

    def set_report(self, report: dict[str, Any] | None) -> None:
        """Read the map's inputs from a report (``None`` empties the map) and show the
        whole test."""
        self._model = build_model(report)
        self._trial = None
        self.updateGeometry()
        self.update()

    @property
    def model(self) -> MapModel:
        return self._model

    @property
    def aspect(self) -> float:
        return self._model.aspect

    @property
    def note(self) -> str | None:
        """The report's note about the marks (a moving target's end position missing)."""
        return self._model.note

    # -- what is shown ------------------------------------------------------

    def set_overlays(
        self, *, targets: bool | None = None, path: bool | None = None, heat: bool | None = None
    ) -> None:
        """Turn overlays on or off (``None`` leaves one as it is)."""
        for name, value in (("targets", targets), ("path", path), ("heat", heat)):
            if value is not None:
                self._overlays[name] = bool(value)
        self.update()

    def overlays(self) -> dict[str, bool]:
        return dict(self._overlays)

    def set_trial(self, index: int | None) -> None:
        """Show one trial (an index into the report's ``trials``), or the whole test
        for ``None`` / an index that is not there."""
        valid = index is not None and 0 <= index < len(self._model.trials)
        self._trial = index if valid else None
        self.update()

    def trial(self) -> int | None:
        return self._trial

    # -- geometry -----------------------------------------------------------

    def set_fit_to_width(self, on: bool) -> None:
        """Let the height follow the width (at the canvas's aspect) instead of filling
        whatever height the layout gives."""
        self._fit_to_width = on
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred if on else QSizePolicy.Policy.Expanding,
        )
        policy = self.sizePolicy()
        policy.setHeightForWidth(on)
        self.setSizePolicy(policy)
        self.updateGeometry()

    def hasHeightForWidth(self) -> bool:  # noqa: N802 (Qt naming)
        return self._fit_to_width

    def heightForWidth(self, width: int) -> int:  # noqa: N802 (Qt naming)
        # A layout asks with the width it has, not the width the widget will take.
        width = min(width, self.maximumWidth())
        return round(max(0, width - 2 * MARGIN) / self._model.aspect) + 2 * MARGIN

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        width = 640
        return QSize(width, self.heightForWidth(width))

    def canvas_rect(self, area: QRectF | None = None) -> QRectF:
        """The canvas rectangle inside ``area`` (default: this widget): the largest at
        the canvas's aspect, centred."""
        area = area if area is not None else QRectF(self.rect())
        inner = area.adjusted(MARGIN, MARGIN, -MARGIN, -MARGIN)
        width = min(inner.width(), inner.height() * self._model.aspect)
        height = width / self._model.aspect
        rect = QRectF(0, 0, width, height)
        rect.moveCenter(inner.center())
        return rect

    # -- painting -----------------------------------------------------------

    def paintEvent(self, _event: object) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        paint_map(painter, self.canvas_rect(), self._model, trial=self._trial, **self._overlays)
        painter.end()

    def render_to_image(self, size: QSize, overlays: dict[str, bool] | None = None) -> QImage:
        """The map as an image of ``size`` (the PDF's picture). ``overlays`` replaces the
        widget's own switches for this one render (the PDF draws Targets only); the
        selected trial, if any, is drawn as it is on screen."""
        image = QImage(size, QImage.Format.Format_ARGB32)
        image.fill(QColor("#FFFFFF"))
        painter = QPainter(image)
        flags = dict(self._overlays) if overlays is None else {"targets": False, "path": False, "heat": False, **overlays}
        paint_map(painter, self.canvas_rect(QRectF(image.rect())), self._model, trial=self._trial, **flags)
        painter.end()
        return image
