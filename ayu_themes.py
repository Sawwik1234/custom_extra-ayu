"""Theme model: storage, validation and application.

A theme is deliberately plain data (a dict of hex colors + a few numbers), so it
can be exported, imported, duplicated and migrated without code changes.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import ayu_colors as colors
import ayu_files as files
import ayu_state as state
import ayu_theme as theme
from ayu_log import get as _get_logger

_log = _get_logger("themes.model")

FILE_NAME = "themes.json"

THEME_FIELDS = (
    "name",
    "accent",
    "out_bubble",
    "in_bubble",
    "header_color",
    "page_color",
    "bubbles_alpha",
    "created",
)

# Mapping theme field → client color keys applied on top of the current look.
COLOR_MAP = {
    "accent": (
        "key_featuredStickers_addButton",
        "key_chat_messagePanelVoicePressed",
        "key_switch2TrackChecked",
        "key_radioBackgroundChecked",
    ),
    "out_bubble": (
        "key_chat_outBubble",
        "key_chat_outBubbleSelected",
    ),
    "in_bubble": (
        "key_chat_inBubble",
        "key_chat_inBubbleSelected",
    ),
    "header_color": (
        "key_actionBarDefault",
        "key_actionBarDefaultSelector",
    ),
    "page_color": (
        "key_windowBackgroundGray",
    ),
}


def load_all() -> List[Dict[str, Any]]:
    raw = files.read_json(FILE_NAME, {})
    items = raw.get("themes") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        return []
    _log.verbose("themes loaded: %d item(s)", len(items))
    cleaned: List[Dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict) and item.get("name"):
            cleaned.append(_normalize(item))
    return cleaned


def save_all(themes: List[Dict[str, Any]]) -> bool:
    ok = files.write_json(FILE_NAME, {"version": 1, "themes": themes})
    _log.debug("themes saved: %d item(s), ok=%s", len(themes), ok)
    return ok


def _normalize(item: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for field in THEME_FIELDS:
        result[field] = item.get(field, "")
    result["name"] = str(result["name"])[:40]
    for field in ("accent", "out_bubble", "in_bubble", "header_color", "page_color"):
        value = colors.parse(str(result.get(field) or ""), 0xFF7C4DFF)
        result[field] = colors.to_hex(value or 0xFF7C4DFF)
    try:
        result["bubbles_alpha"] = max(20, min(100, int(item.get("bubbles_alpha", 100))))
    except (TypeError, ValueError):
        result["bubbles_alpha"] = 100
    if not result.get("created"):
        result["created"] = int(time.time())
    return result


def create(name: str, base: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = dict(base or {})
    data["name"] = name
    data["created"] = int(time.time())
    return _normalize(data)


def remove(themes: List[Dict[str, Any]], index: int) -> List[Dict[str, Any]]:
    if 0 <= index < len(themes):
        return themes[:index] + themes[index + 1:]
    return themes


def find_index(themes: List[Dict[str, Any]], name: str) -> int:
    for index, item in enumerate(themes):
        if item.get("name") == name:
            return index
    return -1


# ---------------------------------------------------------------------------
# Applying
# ---------------------------------------------------------------------------
def apply(item: Dict[str, Any]) -> int:
    """Apply a theme to the current look. Returns the number of color keys."""
    if not theme.available():
        state.note_error("theme API unavailable")
        _log.warning("cannot apply theme %s: color API unavailable", item.get("name"))
        return 0
    theme.revert()
    applied = 0
    alpha = max(20, min(100, int(item.get("bubbles_alpha", 100)))) / 100.0
    for field, keys in COLOR_MAP.items():
        value = colors.parse(str(item.get(field) or ""), None)
        if value is None:
            continue
        if field in ("out_bubble", "in_bubble"):
            value = colors.alpha_percent(value, int(round(255 * alpha)))
        for key_name in keys:
            if theme.set_color(key_name, value):
                applied += 1
    if applied:
        theme.refresh_after_apply()
    _log.info("theme applied: %s (%d color key(s))", item.get("name"), applied)
    state.count_hook_event()
    return applied


def read_current_look() -> Dict[str, Any]:
    """Snapshot the colors the plugin cares about, to seed a new theme."""
    snapshot: Dict[str, Any] = {}
    field_to_key = {
        "accent": "key_featuredStickers_addButton",
        "out_bubble": "key_chat_outBubble",
        "in_bubble": "key_chat_inBubble",
        "header_color": "key_actionBarDefault",
        "page_color": "key_windowBackgroundGray",
    }
    for field, key_name in field_to_key.items():
        snapshot[field] = colors.to_hex(theme.current(key_name, 0xFF7C4DFF))
    snapshot["bubbles_alpha"] = 100
    return snapshot


def readability_warning(item: Dict[str, Any]) -> str:
    """Plain-language warning when a theme is hard to read."""
    page = colors.parse(str(item.get("page_color") or ""), 0xFF101014) or 0xFF101014
    out_bubble = colors.parse(str(item.get("out_bubble") or ""), 0xFF7C4DFF) or 0xFF7C4DFF
    if colors.contrast(page, out_bubble) < 2.0:
        return "low contrast between bubbles and background"
    return ""
