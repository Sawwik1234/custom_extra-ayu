"""Animated gradient background.

The shader is created once per size; per frame we only translate a canvas
buffer, so the cost is one drawRect with a cached shader.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from core import colors, javabridge
from wallpaper.renderers.base import Renderer, dim_color, new_paint


class GradientRenderer(Renderer):
    kind = "gradient"

    def __init__(self) -> None:
        super().__init__()
        self.stops: List[int] = [0xFF0B1026, 0xFF1B3A6B, 0xFF4A2C8F]
        self.style = "drift"
        self.dim = 0
        self._shader: Optional[Any] = None
        self._paint: Optional[Any] = None
        self._shift = 0.0

    def configure(self, settings: Dict[str, Any]) -> None:
        super().configure(settings)
        stops = settings.get("stops") or self.stops
        self.stops = [int(stop) for stop in stops][:4] or self.stops
        self.style = str(settings.get("style") or "drift")
        self.dim = int(settings.get("dim") or 0)
        self._shader = None

    def prepare(self, width: int, height: int) -> None:
        super().prepare(width, height)
        self._shader = None

    # -- shader -------------------------------------------------------------
    def _build_shader(self) -> Any:
        if self._shader is not None:
            return self._shader
        gradient_class = javabridge.find_class("android.graphics.LinearGradient")
        if gradient_class is None:
            return None
        width = self.width * 2
        height = self.height * 2
        palette = [dim_color(color, self.dim) for color in self.stops]
        while len(palette) < 2:
            palette.append(palette[0])
        positions = [float(index) / (len(palette) - 1) for index in range(len(palette))]
        try:
            self._shader = gradient_class(
                0,
                0,
                float(width),
                float(height),
                palette,
                positions,
                gradient_class.TileMode.CLAMP if hasattr(gradient_class, "TileMode") else 0,
            )
        except Exception:
            try:
                self._shader = gradient_class(0, 0, float(width), float(height), palette, positions, 0)
            except Exception:
                self._shader = None
        return self._shader

    # -- frame --------------------------------------------------------------
    def draw(self, canvas: Any, width: int, height: int, delta: float) -> bool:
        time_value = self.advance(delta)
        paint = self.paint()
        if paint is None or canvas is None:
            return False

        shader = self._build_shader()
        if shader is None:
            return self._draw_solid_fallback(canvas, width, height, paint)

        try:
            paint.setShader(shader)
        except Exception:
            return self._draw_solid_fallback(canvas, width, height, paint)

        if self.style == "pulse":
            phase = (math.sin(time_value * 0.9) + 1.0) * 0.5
            alpha = int(200 + 55 * phase)
            try:
                paint.setAlpha(alpha)
            except Exception:
                pass
        else:
            try:
                paint.setAlpha(255)
            except Exception:
                pass

        offset_x = 0.0
        offset_y = 0.0
        if self.style == "drift":
            offset_x = math.sin(time_value * 0.12) * width * 0.18
            offset_y = math.cos(time_value * 0.09) * height * 0.12
        elif self.style == "pulse":
            zoom = 1.0 + math.sin(time_value * 0.7) * 0.04
            offset_x = -width * (zoom - 1.0) * 0.5
            offset_y = -height * (zoom - 1.0) * 0.5

        saved = False
        try:
            canvas.save()
            saved = True
            if self.style == "pulse":
                zoom = 1.0 + math.sin(time_value * 0.7) * 0.04
                canvas.scale(zoom, zoom, width * 0.5, height * 0.5)
            canvas.translate(offset_x, offset_y)
            canvas.drawRect(0.0, 0.0, float(width), float(height), paint)
        except Exception:
            return False
        finally:
            if saved:
                try:
                    canvas.restore()
                except Exception:
                    pass
        return True

    def _draw_solid_fallback(self, canvas: Any, width: int, height: int, paint: Any) -> bool:
        try:
            paint.setShader(None)
        except Exception:
            pass
        try:
            paint.setColor(dim_color(self.stops[0] if self.stops else 0xFF101014, self.dim))
            canvas.drawRect(0.0, 0.0, float(width), float(height), paint)
            return True
        except Exception:
            return False

    def release(self) -> None:
        self._shader = None
        super().release()
