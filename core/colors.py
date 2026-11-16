"""Color parsing and blending helpers.

Colors are handled as Python ints (0xAARRGGBB) and converted to Java ints only
at the very edge, so the maths stays cheap.
"""

from __future__ import annotations

from typing import Optional, Tuple

MASK = 0xFFFFFFFF


def parse(value: str, fallback: Optional[int] = None) -> Optional[int]:
    """Parse ``#RGB``, ``#RRGGBB`` or ``#AARRGGBB`` (``#`` optional)."""
    if value is None:
        return fallback
    text = str(value).strip().lstrip("#")
    if not text:
        return fallback
    try:
        if len(text) == 3:
            text = "".join(ch * 2 for ch in text)
        if len(text) == 6:
            text = "FF" + text
        if len(text) != 8:
            return fallback
        return int(text, 16) & MASK
    except ValueError:
        return fallback


def to_hex(color: int, with_alpha: bool = False) -> str:
    color &= MASK
    if with_alpha:
        return "#%08X" % color
    return "#%06X" % (color & 0xFFFFFF)


def alpha(color: int) -> int:
    return (color >> 24) & 0xFF


def rgb(color: int) -> Tuple[int, int, int]:
    return ((color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF)


def with_alpha(color: int, new_alpha: int) -> int:
    new_alpha = max(0, min(255, int(new_alpha)))
    return (color & 0xFFFFFF) | (new_alpha << 24)


def alpha_percent(color: int, percent: int) -> int:
    return with_alpha(color, round(255 * max(0, min(100, int(percent))) / 100))


def mix(first: int, second: int, ratio: float) -> int:
    """Linear interpolation, ``ratio`` 0 → first, 1 → second."""
    ratio = max(0.0, min(1.0, float(ratio)))
    a1, r1, g1, b1 = alpha(first), *rgb(first)
    a2, r2, g2, b2 = alpha(second), *rgb(second)
    a = round(a1 + (a2 - a1) * ratio)
    r = round(r1 + (r2 - r1) * ratio)
    g = round(g1 + (g2 - g1) * ratio)
    b = round(b1 + (b2 - b1) * ratio)
    return (a << 24) | (r << 16) | (g << 8) | b


def darken(color: int, ratio: float) -> int:
    return mix(color, 0xFF000000, ratio)


def lighten(color: int, ratio: float) -> int:
    return mix(color, 0xFFFFFFFF, ratio)


def luminance(color: int) -> float:
    """Relative luminance 0..1, used for readability checks."""
    r, g, b = rgb(color)

    def channel(value: int) -> float:
        value = value / 255.0
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def readable_text(background: int) -> int:
    """Black or white, whichever reads better on ``background``."""
    return 0xFF000000 if luminance(background) > 0.45 else 0xFFFFFFFF


def contrast(first: int, second: int) -> float:
    a = luminance(first) + 0.05
    b = luminance(second) + 0.05
    return max(a, b) / min(a, b)
