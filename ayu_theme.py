"""Read and write Telegram theme colors through reflection.

Everything degrades to a no-op when the theme API is not reachable, and every
change is recorded in an undo log so "reset" restores exactly what the plugin
touched.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import ayu_colors as colors; import ayu_javabridge as javabridge
from ayu_log import get as _get_logger

_log = _get_logger("core.theme")

# Values applied by the plugin: (key, original_color, applied_color).
_applied: List[Tuple[str, int, int]] = []
_theme_available: Optional[bool] = None


def _theme_class() -> Optional[Any]:
    return javabridge.cls("Theme")


def available() -> bool:
    global _theme_available
    if _theme_available is None:
        _theme_available = _theme_class() is not None
    return bool(_theme_available)


def color_key(name: str) -> Optional[int]:
    theme = _theme_class()
    if theme is None:
        return None
    try:
        return int(getattr(theme, name))
    except Exception:
        return None


def _name_of(key: Any) -> Optional[str]:
    theme = _theme_class()
    if theme is None:
        return None
    try:
        return theme.getColorKeyName(int(key))
    except Exception:
        return None


def current(key_name: str, default: int = 0) -> int:
    key = color_key(key_name)
    if key is None:
        return default
    theme = _theme_class()
    try:
        return int(theme.getColor(key)) & 0xFFFFFFFF
    except Exception:
        try:
            return int(theme.getColor(key, 0)) & 0xFFFFFFFF
        except Exception:
            return default


def set_color(key_name: str, value: int) -> bool:
    key = color_key(key_name)
    theme = _theme_class()
    if key is None or theme is None:
        _log.once("theme-missing-%s" % key_name, "color key %s unavailable", key_name)
        return False
    before = current(key_name, 0)
    try:
        theme.setColor(key, int(value) & 0xFFFFFFFF, False)
    except Exception:
        try:
            theme.setColor(key, int(value) & 0xFFFFFFFF, 0, False)
        except Exception as error:
            _note("setColor failed for %s: %s" % (key_name, error))
            return False
    _remember(key_name, before, int(value) & 0xFFFFFFFF)
    _log.verbose("color %s: %s -> %s", key_name, colors.to_hex(before), colors.to_hex(int(value)))
    return True


def _remember(key_name: str, before: int, after: int) -> None:
    for index, entry in enumerate(_applied):
        if entry[0] == key_name:
            _applied[index] = (key_name, entry[1], after)
            return
    _applied.append((key_name, before, after))


def is_dark() -> bool:
    theme = _theme_class()
    if theme is None:
        return True
    try:
        return bool(theme.isCurrentThemeDark())
    except Exception:
        try:
            return colors.luminance(current("key_windowBackgroundWhite", 0xFFFFFFFF)) < 0.4
        except Exception:
            return True


def refresh_after_apply() -> None:
    theme = _theme_class()
    if theme is None:
        return
    for method_name in ("reloadAllResources", "applyTheme", "refreshTheme"):
        method = getattr(theme, method_name, None)
        if method is None:
            continue
        try:
            method()
            return
        except TypeError:
            continue
        except Exception:
            continue


def revert() -> int:
    """Restore every color the plugin changed. Returns the number of keys."""
    restored = 0
    for key_name, original, _applied_value in reversed(_applied):
        if set_color_raw(key_name, original):
            restored += 1
    _applied.clear()
    refresh_after_apply()
    if restored:
        _log.info("theme colors restored (%d key(s))", restored)
    return restored


def set_color_raw(key_name: str, value: int) -> bool:
    key = color_key(key_name)
    theme = _theme_class()
    if key is None or theme is None:
        return False
    try:
        theme.setColor(key, int(value) & 0xFFFFFFFF, False)
        return True
    except Exception:
        return False


def applied_keys() -> int:
    return len(_applied)


def _note(message: str) -> None:
    _log.warning(message)
