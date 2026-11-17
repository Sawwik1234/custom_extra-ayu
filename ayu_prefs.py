"""Typed access to plugin settings.

All persisted keys and their defaults live in :data:`DEFAULTS` so that
validation, clamping, export and reset happen in one place. Values are cached in
memory, because setting rows read them on every bind.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

# Rendering kinds.
KIND_GRADIENT = "gradient"
KIND_PARALLAX = "parallax"
KIND_PARTICLES = "particles"
KIND_VIDEO = "video"

# Background sources.
SOURCE_BUILTIN = "builtin"
SOURCE_FILE = "file"
SOURCE_URL = "url"

# Skin modes.
SKIN_AUTO = "auto"
SKIN_TINT = "tint"
SKIN_TEXTURE = "texture"

# Particle effects.
PARTICLES_SNOW = "snow"
PARTICLES_STARS = "stars"
PARTICLES_BUBBLES = "bubbles"
PARTICLES_RAIN = "rain"

# Integer settings are clamped to ``(minimum, maximum)``.
INT_BOUNDS: Dict[str, tuple] = {
    "wallpaper_dim": (0, 100),
    "wallpaper_tint": (0, 100),
    "wallpaper_blur": (0, 25),
    "wallpaper_speed": (10, 300),
    "wallpaper_scale": (50, 200),
    "wallpaper_offset_x": (-100, 100),
    "wallpaper_offset_y": (-100, 100),
    "wallpaper_fade_duration": (0, 2000),
    "particles_count": (0, 400),
    "particles_size": (20, 300),
    "particles_speed": (10, 300),
    "particles_alpha": (5, 100),
    "theme_bubbles_alpha": (20, 100),
    "perf_fps": (15, 60),
    "perf_quality": (25, 100),
    "perf_idle_delay": (0, 120),
    "theme_index": (0, 999),
}

DEFAULTS: Dict[str, Any] = {
    # --- wallpaper ---------------------------------------------------------
    "wallpaper_enabled": True,
    "wallpaper_kind": KIND_GRADIENT,
    "wallpaper_source": SOURCE_BUILTIN,
    "wallpaper_builtin": "ayu_aurora",
    "wallpaper_url": "",
    "wallpaper_file": "",
    "wallpaper_dim": 35,
    "wallpaper_tint": 20,
    "wallpaper_blur": 0,
    "wallpaper_speed": 100,
    "wallpaper_scale": 100,
    "wallpaper_offset_x": 0,
    "wallpaper_offset_y": 0,
    "wallpaper_fade": True,
    "wallpaper_fade_duration": 320,
    "wallpaper_apply_chat": True,
    "wallpaper_apply_dialogs": True,
    "wallpaper_apply_everywhere": False,
    # --- particles ---------------------------------------------------------
    "particles_type": PARTICLES_SNOW,
    "particles_count": 90,
    "particles_size": 100,
    "particles_speed": 100,
    "particles_alpha": 70,
    "particles_color": "#FFFFFF",
    # --- themes ------------------------------------------------------------
    "theme_active": "",
    "theme_index": 0,
    "theme_accent": "#7C4DFF",
    "theme_out_bubble": "#7C4DFF",
    "theme_in_bubble": "#212121",
    "theme_header_color": "#1B1B1F",
    "theme_page_color": "#101014",
    "theme_bubbles_alpha": 100,
    # --- skins -------------------------------------------------------------
    "skins_enabled": False,
    "skins_mode": SKIN_AUTO,
    "skin_active": "",
    # --- performance -------------------------------------------------------
    "perf_fps": 30,
    "perf_quality": 100,
    "perf_pause_scroll": True,
    "perf_pause_idle": True,
    "perf_idle_delay": 15,
    "perf_pause_background": True,
    "perf_eco": False,
    # --- diagnostics -------------------------------------------------------
    "diag_debug": False,
    "diag_hook_events": 0,
    "diag_last_error": "",
}

# Keys that must not be wiped by "reset all" (runtime counters).
RESET_EXCLUDE = ("diag_hook_events",)


def clamp_int(key: str, value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = int(DEFAULTS.get(key, 0))
    bounds = INT_BOUNDS.get(key)
    if bounds:
        low, high = bounds
        number = max(low, min(high, number))
    return number


class Prefs:
    """Cached, validated view over the host settings storage."""

    def __init__(self, plugin: Any) -> None:
        self._plugin = plugin
        self._cache: Dict[str, Any] = {}

    # -- plumbing -----------------------------------------------------------
    def raw(self, key: str, default: Any = None) -> Any:
        try:
            return self._plugin.get_setting(key, default)
        except Exception:
            return default

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._cache:
            return self._cache[key]
        fallback = DEFAULTS.get(key, default)
        value = self.raw(key, fallback)
        if key in INT_BOUNDS:
            value = clamp_int(key, value)
        elif isinstance(fallback, bool):
            value = bool(value)
        self._cache[key] = value
        return value

    def set(self, key: str, value: Any, reload_settings: bool = False) -> None:
        if key in INT_BOUNDS:
            value = clamp_int(key, value)
        elif isinstance(DEFAULTS.get(key), bool):
            value = bool(value)
        self._cache[key] = value
        try:
            self._plugin.set_setting(key, value, reload_settings=reload_settings)
        except TypeError:
            # Older SDKs without the keyword argument.
            self._plugin.set_setting(key, value)

    def invalidate(self, key: Optional[str] = None) -> None:
        if key is None:
            self._cache.clear()
        else:
            self._cache.pop(key, None)

    # -- convenience --------------------------------------------------------
    def bool(self, key: str) -> bool:
        return bool(self.get(key))

    def int(self, key: str) -> int:
        return clamp_int(key, self.get(key))

    def text(self, key: str) -> str:
        value = self.get(key)
        return "" if value is None else str(value)

    def reset_all(self) -> None:
        for key, value in DEFAULTS.items():
            if key not in RESET_EXCLUDE:
                self.set(key, value)
        self.invalidate()
