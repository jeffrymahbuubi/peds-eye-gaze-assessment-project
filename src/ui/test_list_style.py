"""The Test List's own style sheets (SPEC-test-list-visual-identity.md, direction A "Ledger";
wireframe ``docs/wireframes/test-list-alt-a.md``).

Look only: tokens of :mod:`~src.ui.design_tokens`, the existing button tiers and the existing
card. Both sheets are set on the Test List's own widgets, so every other dashboard table and card
keeps the global rules of :mod:`~src.ui.wtmh_controls` and :mod:`~src.ui.wtmh_theme`.
"""

from __future__ import annotations

from .design_tokens import BORDER_SUBTLE

# The theme pads every header section by 6 px 8 px, the hidden vertical header included, which makes
# each row about 13 px taller than its text. The Date column has 16 px on its right in the header and
# in the cells, so the right-aligned label and the dates share one edge and the sort arrow fits
# beside the label.
TABLE_STYLE = """
QHeaderView::section:vertical { padding: 0px; border: none; }
QHeaderView::section:horizontal:last { padding-right: 16px; }
QTableWidget#wtmhTestTable::item { padding: 4px 16px 4px 8px; }
"""

# The command panel: its buttons are the tertiary tier with a left-aligned label, and a rule is a
# 1 px line in the card's own border colour.
PANEL_STYLE = f"""
QPushButton#wtmhTertiary {{ text-align: left; }}
QFrame#wtmhTestRule {{ background: {BORDER_SUBTLE}; border: none; }}
"""
