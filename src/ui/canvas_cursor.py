"""The gaze cursor of the task canvas: its look (a small hollow ring with a contrasting
fringe) and the clamp that keeps it whole inside the widget. Split out of
:mod:`src.ui.canvas` to keep that file under the size limit; Qt-free.
"""

from __future__ import annotations

# The gaze cursor is a small hollow ring, modelled on Gazepoint Control's own
# marker (SPEC-gaze-cursor-redesign.md S4.3, reference screenshots at
# resources/images/gaze-cursor-from-calib/). Hollow and small on purpose: it no
# longer occludes the target underneath it, which matters most at exactly the
# moment the child is on target and the dwell ring is filling. It must stay
# visually distinct from that dwell arc (8px stroke, target-sized radius) so it
# never reads as a second, smaller progress indicator.
_CURSOR_RADIUS_PX = 5.0
_CURSOR_STROKE_PX = 2.0

# The ring is drawn twice: a wider halo underneath, then the core stroke on
# top, leaving a contrasting fringe on both sides of the core line. This is
# what makes one small marker legible on *any* backdrop without per-theme
# tuning (SPEC-gaze-cursor-redesign.md S10) -- a single-colour ring cannot be,
# and the first attempt proved it: a dark-green core on the forest theme's
# light-green background, among dark-green grid outlines drawn in the same
# `cursor_color`, was reported as blending in and hard to notice.
#
# Copying Gazepoint Control's *colour* was the error there. Their saturated
# green works because their backdrop is near-black; the transferable principle
# is maximum contrast against the background, not the hue itself.
# The dark fringe is the load-bearing half, and it was chosen by measurement,
# not taste: rendered against the real forest scene, a white halo round a
# theme-coloured core scored 32205 against the plain ring's 30832 -- a 4%
# improvement, because white fringe on a near-white background adds almost no
# ink. Dark fringe with a white core scored 53363, +73%. The core then carries
# legibility on dark themes, where the fringe is what disappears. Both values
# are deliberately theme-independent: per-theme accent colours are exactly what
# produced the blending complaint.
_CURSOR_HALO_STROKE_PX = 5.0
_CURSOR_HALO_COLOR = "#102010"
_CURSOR_CORE_COLOR = "#ffffff"

# A ring lays down far less ink than the filled disc it replaces, so it needs
# more alpha than the old 200/70 pair to stay as legible.
_CURSOR_ALPHA = 235
_CURSOR_ALPHA_DIM = 110


def _clamp_to_canvas(x: float, y: float, w: int, h: int) -> tuple[float, float, bool]:
    """Pull a cursor position inside the canvas, reporting whether it had to.

    Off-canvas gaze no longer reaches here -- the cursor freezes at its last
    on-canvas position instead (see :meth:`TaskCanvas._cursor_draw_position`),
    so this is now a safety net rather than the main mechanism: it keeps a ring
    sitting exactly on the boundary drawn whole instead of half-clipped by the
    widget edge, and guards against rounding at 0.0/1.0.

    Inset by the cursor's own radius *plus half its stroke* so the clamped ring
    is drawn whole, not half-clipped by the boundary -- a stroke straddles the
    path it is drawn on, so radius alone would leave the outer half of the line
    outside the widget. The returned flag is what lets the caller show a
    clamped cursor differently from a real in-canvas one -- without it, "gaze
    at the very edge" and "gaze left the canvas" would be identical.
    """
    r = _CURSOR_RADIUS_PX + max(_CURSOR_STROKE_PX, _CURSOR_HALO_STROKE_PX) / 2.0
    cx = min(max(x, r), max(float(w) - r, r))
    cy = min(max(y, r), max(float(h) - r, r))
    return cx, cy, (cx != x or cy != y)
