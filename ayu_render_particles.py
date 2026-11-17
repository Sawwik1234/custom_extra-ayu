"""Particle background: snow, stars, bubbles and rain.

Performance rules that matter here:

* particles live in preallocated parallel lists of floats — no per-frame objects;
* the ``Paint`` is created once and only its alpha changes;
* when a particle leaves the screen it is recycled in place, never re-created;
* the count is clamped by the settings layer, so a wrong value cannot freeze the UI.
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List

from ayu_render_base import Renderer, clamp, dim_color

SNOW = "snow"
STARS = "stars"
BUBBLES = "bubbles"
RAIN = "rain"


class ParticleRenderer(Renderer):
    kind = "particles"

    def __init__(self) -> None:
        super().__init__()
        self.effect = SNOW
        self.count = 90
        self.size = 100
        self.alpha = 70
        self.tint = 0xFFFFFFFF
        self.dim = 0
        self._x: List[float] = []
        self._y: List[float] = []
        self._vx: List[float] = []
        self._vy: List[float] = []
        self._r: List[float] = []
        self._phase: List[float] = []
        self._random = random.Random()

    # -- configuration ------------------------------------------------------
    def configure(self, settings: Dict[str, Any]) -> None:
        super().configure(settings)
        self.effect = str(settings.get("effect") or SNOW)
        self.count = max(0, min(400, int(settings.get("count", 90))))
        self.size = max(20, min(300, int(settings.get("size", 100))))
        self.alpha = max(5, min(100, int(settings.get("alpha", 70))))
        self.tint = int(settings.get("color") or 0xFFFFFFFF)
        self.dim = int(settings.get("dim") or 0)
        self._x = []
        self._y = []
        self._vx = []
        self._vy = []
        self._r = []
        self._phase = []

    def prepare(self, width: int, height: int) -> None:
        super().prepare(width, height)
        self._spawn_all()

    def _spawn_all(self) -> None:
        self._x = [0.0] * self.count
        self._y = [0.0] * self.count
        self._vx = [0.0] * self.count
        self._vy = [0.0] * self.count
        self._r = [0.0] * self.count
        self._phase = [0.0] * self.count
        for index in range(self.count):
            self._spawn(index, initial=True)

    def _spawn(self, index: int, initial: bool = False) -> None:
        width = float(self.width)
        height = float(self.height)
        base_radius = max(1.0, min(6.0, self.size / 40.0))

        if self.effect == STARS:
            self._x[index] = self._random.uniform(0.0, width)
            self._y[index] = self._random.uniform(0.0, height)
            self._vx[index] = self._random.uniform(-2.0, 2.0)
            self._vy[index] = self._random.uniform(-1.0, 1.0)
            self._r[index] = base_radius * self._random.uniform(0.4, 1.1)
            self._phase[index] = self._random.uniform(0.0, math.tau)
        elif self.effect == BUBBLES:
            self._x[index] = self._random.uniform(0.0, width)
            self._y[index] = height + self._random.uniform(0.0, height) if initial else height + base_radius
            self._vx[index] = self._random.uniform(-6.0, 6.0)
            self._vy[index] = -self._random.uniform(18.0, 48.0)
            self._r[index] = base_radius * self._random.uniform(0.7, 1.6)
            self._phase[index] = self._random.uniform(0.0, math.tau)
        elif self.effect == RAIN:
            self._x[index] = self._random.uniform(0.0, width)
            self._y[index] = self._random.uniform(0.0, height) if initial else -base_radius * 2
            self._vx[index] = -self._random.uniform(20.0, 60.0)
            self._vy[index] = self._random.uniform(520.0, 900.0)
            self._r[index] = base_radius * self._random.uniform(0.35, 0.7)
            self._phase[index] = 0.0
        else:  # snow
            self._x[index] = self._random.uniform(0.0, width)
            self._y[index] = self._random.uniform(0.0, height) if initial else -base_radius * 2
            self._vx[index] = self._random.uniform(-14.0, 14.0)
            self._vy[index] = self._random.uniform(24.0, 70.0)
            self._r[index] = base_radius * self._random.uniform(0.5, 1.3)
            self._phase[index] = self._random.uniform(0.0, math.tau)

    # -- frame --------------------------------------------------------------
    def draw(self, canvas: Any, width: int, height: int, delta: float) -> bool:
        self.advance(delta)
        paint = self.paint()
        if paint is None or canvas is None:
            return False
        if not self.count:
            return True

        step = clamp(float(delta), 0.0, 0.05)
        width_f = float(width)
        height_f = float(height)
        density = self.size / 100.0
        base_alpha = int(255 * self.alpha / 100.0)
        tint = dim_color(self.tint, self.dim)

        try:
            paint.setStyle(0)  # FILL
            paint.setShader(None)
            paint.setColor(tint & 0xFFFFFFFF)
        except Exception:
            pass

        for index in range(self.count):
            x = self._x[index] + self._vx[index] * step * self.speed
            y = self._y[index] + self._vy[index] * step * self.speed
            radius = self._r[index] * density

            if self.effect == STARS:
                self._phase[index] += step * 1.6 * self.speed
                twinkle = 0.55 + 0.45 * math.sin(self._phase[index])
                alpha = int(base_alpha * twinkle)
            elif self.effect == BUBBLES:
                self._phase[index] += step * 2.0
                x += math.sin(self._phase[index]) * 8.0
                alpha = base_alpha
            elif self.effect == RAIN:
                alpha = base_alpha
            else:
                self._phase[index] += step * 1.1
                x += math.sin(self._phase[index]) * 12.0
                alpha = base_alpha

            # Recycle instead of allocating.
            if y > height_f + radius * 2:
                self._spawn(index)
                continue
            if y < -radius * 4 and (self.effect == BUBBLES or self.effect == STARS):
                self._spawn(index)
                continue
            if x < -radius * 4 or x > width_f + radius * 4:
                self._spawn(index)
                continue

            self._x[index] = x
            self._y[index] = y

            try:
                paint.setAlpha(max(0, min(255, alpha)))
            except Exception:
                pass

            try:
                if self.effect == RAIN:
                    canvas.drawLine(x, y, x - radius * 1.6, y + radius * 9.0, paint)
                else:
                    canvas.drawCircle(x, y, radius, paint)
            except Exception:
                return False

        return True

    def release(self) -> None:
        self._x = []
        self._y = []
        self._vx = []
        self._vy = []
        self._r = []
        self._phase = []
        super().release()
