"""WCAG colour maths for the tests that pin readability (not a test module)."""

from __future__ import annotations

from PySide6.QtGui import QColor


def luminance(colour: QColor) -> float:
    """WCAG relative luminance of ``colour``."""

    def linear(value: int) -> float:
        v = value / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    return 0.2126 * linear(colour.red()) + 0.7152 * linear(colour.green()) + 0.0722 * linear(colour.blue())


def contrast(a: QColor, b: QColor) -> float:
    """WCAG contrast ratio of two colours (1 to 21)."""
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)
