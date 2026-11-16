"""Renderer protocol and shared helpers.

A renderer never touches settings directly on every frame: :meth:`configure` is
called when the background host is attached or when the user changes something,
and the frame loop only reads plain scalars.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from core import colors, javabridge


def new_paint(flags: int = 1) -> Optional[Any]:
    """Create a Java ``Paint`` (flag 1 = anti-alias)."""
    paint_class = javabridge.find_class("android.graphics.Paint")
    if paint_class is None:
        return None
    try:
        paint = paint_class(flags)
        return paint
    except Exception:
        try:
            return paint_class()
        except Exception:
            return None


def set_paint_color(paint: Any, color: int) -> None:
    try:
        paint.setColor(int(color) & 0xFFFFFFFF)
    except Exception:
        pass


def set_paint_alpha(paint: Any, alpha: int) -> None:
    try:
        paint.setAlpha(max(0, min(255, int(alpha))))
    except Exception:
        pass


class Renderer:
    """Base class. Subclasses override :meth:`prepare`, :meth:`draw`."""

    kind = "base"

    def __init__(self) -> None:
        self.width = 0
        self.height = 0
        self.time = 0.0
        self.speed = 1.0
        self._paint: Optional[Any] = None

    # -- lifecycle ----------------------------------------------------------
    def configure(self, settings: Dict[str, Any]) -> None:
        self.speed = max(0.1, float(settings.get("speed", 100)) / 100.0)

    def prepare(self, width: int, height: int) -> None:
        self.width = max(1, int(width))
        self.height = max(1, int(height))

    def draw(self, canvas: Any, width: int, height: int, delta: float) -> bool:
        raise NotImplementedError

    def release(self) -> None:
        self._paint = None

    # -- helpers ------------------------------------------------------------
    def advance(self, delta: float) -> float:
        step = max(0.0, min(0.1, float(delta))) * self.speed
        self.time += step
        return self.time

    def paint(self) -> Optional[Any]:
        if self._paint is None:
            self._paint = new_paint()
        return self._paint


def clamp(value: float, low: float, high: float) -> float:
    return low if value < low else (high if value > high else value)


def dim_color(color: int, percent: int) -> int:
    """Apply ``percent`` of black on top of a color."""
    if percent <= 0:
        return color
    ratio = max(0, min(100, percent)) / 100.0
    return colors.mix(color, 0xFF000000, ratio)
