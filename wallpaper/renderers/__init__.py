"""Renderer factory.

Keeps the mapping "settings → renderer instance" in one place so the host does
not grow another ``if`` chain.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from core import prefs
from wallpaper.renderers.base import Renderer
from wallpaper.renderers.gradient import GradientRenderer
from wallpaper.renderers.parallax import ParallaxRenderer
from wallpaper.renderers.particles import ParticleRenderer
from wallpaper.renderers.video import VideoRenderer

__all__ = [
    "Renderer",
    "GradientRenderer",
    "ParallaxRenderer",
    "ParticleRenderer",
    "VideoRenderer",
    "create",
    "settings_for",
]


def create(kind: str) -> Renderer:
    if kind == prefs.KIND_PARALLAX:
        return ParallaxRenderer()
    if kind == prefs.KIND_PARTICLES:
        return ParticleRenderer()
    if kind == prefs.KIND_VIDEO:
        return VideoRenderer()
    return GradientRenderer()


def _dark_theme() -> bool:
    from core import theme

    return theme.is_dark()


def settings_for(
    prefs_obj: prefs.Prefs,
    kind: str,
    local_path: Optional[str] = None,
    fallback_color: int = 0xFF101014,
) -> Dict[str, Any]:
    """Everything a renderer needs, resolved once per configuration change."""
    from core import assets, colors

    dim = prefs_obj.int("wallpaper_dim")
    extra = prefs_obj.int("wallpaper_tint") if _dark_theme() else 0

    return {
        "kind": kind,
        "speed": prefs_obj.int("wallpaper_speed"),
        "dim": min(100, dim + extra),
        "scale": prefs_obj.int("wallpaper_scale"),
        "offset_x": prefs_obj.int("wallpaper_offset_x"),
        "offset_y": prefs_obj.int("wallpaper_offset_y"),
        "blur": prefs_obj.int("wallpaper_blur"),
        "path": local_path or "",
        "fallback_color": fallback_color,
        # gradient
        "stops": assets.gradient_colors(prefs_obj),
        "style": assets.gradient_style(prefs_obj),
        # particles
        "effect": prefs_obj.text("particles_type"),
        "count": prefs_obj.int("particles_count"),
        "size": prefs_obj.int("particles_size"),
        "alpha": prefs_obj.int("particles_alpha"),
        "color": colors.parse(prefs_obj.text("particles_color"), 0xFFFFFFFF),
        # video
        "looping": True,
        "muted": True,
    }
