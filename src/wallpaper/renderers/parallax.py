"""Parallax image background.

The bitmap is decoded once at screen size and drawn with a scroll offset that
lags behind the list. Only two matrix operations per frame.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional

from core import colors, images, javabridge
from wallpaper.renderers.base import Renderer, dim_color


class ParallaxRenderer(Renderer):
    kind = "parallax"

    def __init__(self) -> None:
        super().__init__()
        self.path = ""
        self.dim = 0
        self.scale = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.blur = 0
        self._bitmap: Optional[Any] = None
        self._paint: Optional[Any] = None
        self._scroll = 0.0
        self._target_scroll = 0.0
        self._fallback = 0xFF101014

    def configure(self, settings: Dict[str, Any]) -> None:
        super().configure(settings)
        self.path = str(settings.get("path") or "")
        self.dim = int(settings.get("dim") or 0)
        self.scale = max(0.5, float(settings.get("scale", 100)) / 100.0)
        self.offset_x = float(settings.get("offset_x", 0)) / 100.0
        self.offset_y = float(settings.get("offset_y", 0)) / 100.0
        self.blur = int(settings.get("blur") or 0)
        self._fallback = int(settings.get("fallback_color") or 0xFF101014)
        self._bitmap = None

    def prepare(self, width: int, height: int) -> None:
        super().prepare(width, height)
        self._bitmap = None
        if self.path:
            self._bitmap = images.decode(self.path, int(width * self.scale), int(height * self.scale))

    def set_scroll_progress(self, progress: float) -> None:
        """``progress`` in pixels of list offset, fed by the chat hook."""
        self._target_scroll = float(progress)

    # -- frame --------------------------------------------------------------
    def draw(self, canvas: Any, width: int, height: int, delta: float) -> bool:
        self.advance(delta)
        if canvas is None:
            return False

        # Ease the scroll offset so the image never jitters with the list.
        self._scroll += (self._target_scroll - self._scroll) * min(1.0, delta * 8.0)

        if self._bitmap is None:
            return self._draw_fallback(canvas, width, height)

        paint = self.paint()
        if paint is None:
            return False

        try:
            paint.setShader(None)
            paint.setAlpha(255)
        except Exception:
            pass

        try:
            bitmap_width = float(self._bitmap.getWidth())
            bitmap_height = float(self._bitmap.getHeight())
        except Exception:
            return self._draw_fallback(canvas, width, height)

        if bitmap_width <= 0 or bitmap_height <= 0:
            return self._draw_fallback(canvas, width, height)

        # Cover the screen, then add a little overscan for the parallax travel.
        overscan = 1.18
        cover = max(float(width) / bitmap_width, float(height) / bitmap_height) * overscan
        draw_width = bitmap_width * cover
        draw_height = bitmap_height * cover

        left = (float(width) - draw_width) * 0.5
        top = (float(height) - draw_height) * 0.5

        left += self.offset_x * float(width) * 0.5
        top += self.offset_y * float(height) * 0.5

        travel_x = (draw_width - float(width)) * 0.5
        travel_y = (draw_height - float(height)) * 0.5
        drift_x = math.sin(self.time * 0.10) * travel_x * 0.35
        drift_y = math.cos(self.time * 0.08) * travel_y * 0.35
        scroll_y = max(-travel_y, min(travel_y, self._scroll * 0.12))

        left -= drift_x
        top -= drift_y + scroll_y

        try:
            canvas.drawBitmap(self._bitmap, None, _rect(left, top, left + draw_width, top + draw_height), paint)
        except Exception:
            return self._draw_fallback(canvas, width, height)

        if self.dim > 0:
            return self._draw_dim(canvas, width, height)
        return True

    def _draw_dim(self, canvas: Any, width: int, height: int) -> bool:
        paint = self.paint()
        if paint is None:
            return True
        try:
            paint.setShader(None)
            paint.setColor(dim_color(0xFF000000, self.dim) | 0xFF000000)
            paint.setAlpha(int(255 * min(100, self.dim) / 100))
            canvas.drawRect(0.0, 0.0, float(width), float(height), paint)
            return True
        except Exception:
            return True

    def _draw_fallback(self, canvas: Any, width: int, height: int) -> bool:
        paint = self.paint()
        if paint is None:
            return False
        try:
            paint.setShader(None)
            paint.setColor(self._fallback)
            paint.setAlpha(255)
            canvas.drawRect(0.0, 0.0, float(width), float(height), paint)
            return True
        except Exception:
            return False

    def release(self) -> None:
        self._bitmap = None
        super().release()


def _rect(left: float, top: float, right: float, bottom: float) -> Any:
    rect_class = javabridge.find_class("android.graphics.RectF")
    if rect_class is None:
        return None
    try:
        return rect_class(float(left), float(top), float(right), float(bottom))
    except Exception:
        return None
