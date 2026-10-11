"""Idle life of the Choice-making scene (SPEC-scene-cause-effect-task.md N3, 4.4), Qt-free.

Between trials the picture is not frozen: with ``idle_animation`` ``blinks`` (the default, as in
Grid 3) each blinking character shows its eyes closed for about 150 ms at random 2-6 s intervals;
``blinks_bob`` adds a slow sine bob of the balloons and the cloud; ``off`` is a still picture.

:class:`IdleLife` is a small clock-driven state machine: the renderer feeds it elapsed time
(:meth:`~IdleLife.advance`) from the canvas tick, so it stops when the test is paused and runs only
outside an effect (the renderer simply does not advance it during one). Blinks are not logged. A
seeded ``random.Random`` makes it deterministic for tests.
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterable, Mapping

from .choice_scene import DEFAULT_IDLE, IDLE_BLINKS_BOB, IDLE_OFF, SceneManifest

BLINK_MS = 150.0
BLINK_GAP_S = (2.0, 6.0)  # seconds between one blink's end and the next one's start


class IdleLife:
    """Blink and bob state of the scene at time ``t`` (seconds of running idle time)."""

    def __init__(
        self,
        mode: str = DEFAULT_IDLE,
        characters: Iterable[str] = (),
        bobs: Mapping[str, tuple[float, float]] | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.mode = mode
        self.t = 0.0
        self._rng = rng if rng is not None else random.Random()
        self._bobs = dict(bobs or {})
        # character -> [next blink start, blink end]
        self._blink: dict[str, list[float]] = {}
        if mode != IDLE_OFF:
            for character in characters:
                self._blink[character] = [self._gap(), 0.0]
        # Each bobbing object gets its own phase so the balloons and the cloud do not move together.
        self._phase = {object_id: self._rng.random() for object_id in self._bobs}

    @classmethod
    def for_manifest(
        cls, manifest: SceneManifest, mode: str, rng: random.Random | None = None
    ) -> IdleLife:
        """The idle life of every character and bobbing object of ``manifest``."""
        return cls(
            mode,
            [spot.id for spot in manifest.characters()],
            {obj.id: obj.bob for obj in manifest.objects if obj.bob is not None},
            rng,
        )

    def _gap(self) -> float:
        return self.t + self._rng.uniform(*BLINK_GAP_S)

    def advance(self, dt_s: float) -> None:
        """Move idle time on by ``dt_s`` seconds (never backwards)."""
        if dt_s <= 0:
            return
        self.t += dt_s
        for times in self._blink.values():
            if times[1] and self.t >= times[1]:  # the blink is over: wait for the next one
                times[0], times[1] = self._gap(), 0.0
            if not times[1] and self.t >= times[0]:
                times[1] = times[0] + BLINK_MS / 1000.0

    def is_blinking(self, character: str) -> bool:
        times = self._blink.get(character)
        return bool(times and times[1] and times[0] <= self.t < times[1])

    def blinking(self) -> list[str]:
        """Every character whose eyes are closed right now."""
        return [character for character in self._blink if self.is_blinking(character)]

    def bob_offset(self, object_id: str) -> float:
        """The vertical bob of ``object_id`` in scene heights (0 unless the mode is ``blinks_bob``)."""
        bob = self._bobs.get(object_id)
        if self.mode != IDLE_BLINKS_BOB or bob is None:
            return 0.0
        amplitude, period_s = bob
        return amplitude * math.sin(math.tau * (self.t / period_s + self._phase[object_id]))

    def bobbing(self) -> list[str]:
        """The objects that bob in this mode."""
        return list(self._bobs) if self.mode == IDLE_BLINKS_BOB else []
