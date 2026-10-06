"""Entries into the active target (SPEC-compass-task-flow.md 4D.4-1, U10).

An *entry* is the pointer going from outside the target's hitbox to inside it,
counted so the report can tell a child who landed on the target once and stayed
(Compass's "error-free" selection) from one whose gaze wandered on and off. It
is Qt-free and takes the same ``on_target`` flag the dwell logic uses, so grid
cell clipping and the like apply to both alike.

Raw rising edges overcount on a real tracker, so the rule is debounced:

* A frame whose pointer is not valid is ignored: it neither enters, nor exits,
  nor advances the exit timer. ``FPOGV`` is false during saccades and blinks,
  and such a dropout says nothing about where the gaze was.
* The first valid on-target frame while outside is an entry.
* Valid off-target frames while inside end the visit only once the *first* of
  them is at least ``exit_hold_ms`` old (it is a valid off-target frame that
  commits, not the passage of time); an on-target frame before then cancels the
  exit. A return after a committed exit is a new entry.

Measured on a real 18-trial run (SPEC 4D.4-1): naive edges 34, invalid frames
bridged 26, plus a 100 ms hold 21, plus 200 ms 20. 120 ms sits on that plateau
and is the dwell's own hold-grace, so the two never disagree about a flicker.
"""

from __future__ import annotations

from ..inputs.eye_input import DwellConfig

# The dwell selector's tolerated off-target gap (``DwellConfig.hold_grace_ms``).
DEFAULT_EXIT_HOLD_MS: float = DwellConfig().hold_grace_ms

ENTER = "enter"
EXIT = "exit"


class EntryTracker:
    """Counts debounced entries into one target; :meth:`reset` per trial."""

    def __init__(self, exit_hold_ms: float = DEFAULT_EXIT_HOLD_MS) -> None:
        self.exit_hold_ns = int(exit_hold_ms * 1e6)
        self.entries = 0
        self.first_entry_ns: int | None = None
        self._inside = False
        # Time of the first valid off-target frame of the pending exit.
        self._off_since_ns: int | None = None

    @property
    def inside(self) -> bool:
        """Whether the pointer is in a committed visit (a pending exit that
        has not yet reached the hold still counts as inside)."""
        return self._inside

    def reset(self) -> None:
        """Forget everything: a new trial, a new target."""
        self.entries = 0
        self.first_entry_ns = None
        self._inside = False
        self._off_since_ns = None

    def update(self, t_ns: int, valid: bool, on_target: bool) -> str | None:
        """Feed one frame. Returns :data:`ENTER` when this frame is a new entry,
        :data:`EXIT` when it commits an exit, else ``None``."""
        if not valid:
            return None
        if on_target:
            self._off_since_ns = None  # cancels a pending exit
            if self._inside:
                return None
            self._inside = True
            self.entries += 1
            if self.first_entry_ns is None:
                self.first_entry_ns = t_ns
            return ENTER
        if not self._inside:
            return None
        if self._off_since_ns is None:
            self._off_since_ns = t_ns
        if t_ns - self._off_since_ns >= self.exit_hold_ns:
            self._inside = False
            self._off_since_ns = None
            return EXIT
        return None
