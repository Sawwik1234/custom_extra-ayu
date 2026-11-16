"""Applying a skin: tint mode (always available) and texture mode (best effort).

Tint mode only changes color keys through the theme API, so it is safe on every
build. Texture mode replaces drawables on client views and is probed per element:
whatever cannot be bound is simply skipped and reported.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from core import colors, javabridge, state, theme
from core.log import get as _get_logger
from skins import registry

_log = _get_logger("skins.apply")

TINT_KEY_MAP = {
    registry.ELEMENT_OUT: ("key_chat_outBubble", "key_chat_outBubbleSelected"),
    registry.ELEMENT_IN: ("key_chat_inBubble", "key_chat_inBubbleSelected"),
    registry.ELEMENT_PANEL: ("key_chat_messagePanelBackground",),
    registry.ELEMENT_HEADER: ("key_actionBarDefault",),
}

_peer_cache: Dict[str, Any] = {}
_unhooks: Dict[str, Any] = {}


def texture_mode_available() -> bool:
    return javabridge.has("ChatMessageCell")


def resolved_mode(prefs_obj: Any) -> str:
    mode = prefs_obj.text("skins_mode")
    if mode == "auto":
        return "texture" if texture_mode_available() else "tint"
    if mode == "texture" and not texture_mode_available():
        state.note_error("texture mode unavailable, using colors")
        _log.warning("texture mode requested but chat cells are unreachable; using colors")
        return "tint"
    return mode or "tint"


def apply_tints(skin: Optional[registry.Skin], prefs_obj: Any) -> int:
    if not theme.available():
        state.note_error("theme API unavailable for tints")
        return 0
    accents = {
        registry.ELEMENT_OUT: colors.parse(prefs_obj.text("theme_out_bubble"), 0xFF7C4DFF),
        registry.ELEMENT_IN: colors.parse(prefs_obj.text("theme_in_bubble"), 0xFF212121),
        registry.ELEMENT_PANEL: colors.parse(prefs_obj.text("theme_header_color"), 0xFF1B1B1F),
        registry.ELEMENT_HEADER: colors.parse(prefs_obj.text("theme_header_color"), 0xFF1B1B1F),
    }
    applied = 0
    for element, keys in TINT_KEY_MAP.items():
        color = None
        if skin is not None:
            color = skin.tint(element)
        if color is None:
            color = accents.get(element)
        if color is None:
            continue
        for key_name in keys:
            if theme.set_color(key_name, color):
                applied += 1
    if applied:
        theme.refresh_after_apply()
    _log.debug("skin tints applied: %d key(s)", applied)
    return applied


def apply_textures(skin: Optional[registry.Skin], prefs_obj: Any) -> int:
    """Attach bitmap drawables to client views. Returns the bound elements."""
    if skin is None:
        return 0
    bound = 0
    for element in registry.ELEMENTS:
        if not skin.has(element):
            continue
        bitmap = skin.bitmap(element, 512, 512)
        if bitmap is None:
            continue
        drawable = _bitmap_drawable(bitmap)
        if drawable is None:
            continue
        if _bind_element(element, drawable):
            bound += 1
        else:
            _log.once("skin-unbound-%s" % element, "element %s has an image but no attach point", element)
    if bound:
        _log.info("skin textures bound: %d element(s)", bound)
    return bound


def _bitmap_drawable(bitmap: Any) -> Optional[Any]:
    try:
        drawable_class = javabridge.cls("BitmapDrawable")
        if drawable_class is None:
            return None
        context = javabridge.application_context()
        if context is None:
            return None
        return drawable_class(context.getResources(), bitmap)
    except Exception:
        return None


def _bind_element(element: str, drawable: Any) -> bool:
    """Best-effort: set the drawable as a background of the matching surface."""
    from android_utils import run_on_ui_thread  # type: ignore

    targets = _find_targets(element)
    if not targets:
        return False
    ok = False
    for target in targets:
        try:
            run_on_ui_thread(lambda view=target, d=drawable: _set_background(view, d))
            ok = True
        except Exception:
            if _set_background(target, drawable):
                ok = True
    return ok


def _set_background(view: Any, drawable: Any) -> bool:
    try:
        view.setBackground(drawable)
        return True
    except Exception:
        return False


def _find_targets(element: str) -> list:
    """Locate live views for an element; empty when the screen is not open."""
    found: list = []
    try:
        from client_utils import get_last_fragment  # type: ignore

        fragment = get_last_fragment()
    except Exception:
        fragment = None
    if fragment is None:
        return found

    field_names = {
        registry.ELEMENT_PANEL: ("messageEditText", "chatActivityEnterView"),
        registry.ELEMENT_HEADER: ("actionBar",),
        registry.ELEMENT_OUT: ("chatListView",),
        registry.ELEMENT_IN: ("chatListView",),
    }.get(element, ())

    for name in field_names:
        try:
            from hook_utils import get_private_field  # type: ignore

            value = get_private_field(fragment, name)
            if value is not None:
                found.append(value)
        except Exception:
            continue
    return found


def release() -> None:
    _peer_cache.clear()
    _unhooks.clear()
