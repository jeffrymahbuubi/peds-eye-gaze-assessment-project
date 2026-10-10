"""Feedback bus (plan section 5.6).

Feedback (sound, particle animation, progress ring) is abstracted behind a small
interface so the task logic stays GUI-free and testable. The GUI supplies a
PySide6-backed implementation; the headless pipeline and tests use
:class:`NullFeedback`, which just records the events it was asked to play.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class FeedbackBus(ABC):
    """Sink for feedback effects triggered by tasks."""

    @abstractmethod
    def on_target_shown(self, x: float, y: float) -> None: ...

    @abstractmethod
    def on_hit(self, x: float, y: float) -> None: ...

    @abstractmethod
    def on_miss(self, x: float, y: float) -> None: ...

    @abstractmethod
    def on_progress(self, x: float, y: float, progress: float) -> None: ...

    # Choice-making's audio (SPEC-scene-cause-effect-task.md section 9, Q2 = A). Optional: a no-op
    # here, so every other task, ``NullFeedback`` and the headless pipeline are unaffected.

    def on_prompt(self, object_id: str) -> None:  # noqa: B027 - intentional optional no-op hook
        """The spoken prompt of ``object_id`` starts (``PROMPT_START``)."""

    def on_effect(self, object_id: str, modelled: bool) -> None:  # noqa: B027 - optional no-op
        """The effect of ``object_id`` starts with its own sound (``EFFECT_START``)."""

    def on_stop_audio(self) -> None:  # noqa: B027 - intentional optional no-op hook
        """Cut any prompt or effect sound that is playing (a pause, a skip)."""


@dataclass
class NullFeedback(FeedbackBus):
    """No-op feedback that records calls for inspection/testing."""

    events: list[tuple[str, float, float]] = field(default_factory=list)

    def on_target_shown(self, x: float, y: float) -> None:
        self.events.append(("target_shown", x, y))

    def on_hit(self, x: float, y: float) -> None:
        self.events.append(("hit", x, y))

    def on_miss(self, x: float, y: float) -> None:
        self.events.append(("miss", x, y))

    def on_progress(self, x: float, y: float, progress: float) -> None:
        # progress is high-frequency; only the latest is usually of interest.
        self.events.append(("progress", x, y))
