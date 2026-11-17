"""Wallpaper controller: turns settings into attached background hosts.

The controller is the only place that knows how a screen maps to a renderer. It
keeps one :class:`WallpaperHost` per attached screen, reuses it across resumes
and disposes everything on unload.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import ayu_assets as assets
import ayu_engine as engine
import ayu_files as files
import ayu_prefs as prefs
import ayu_state as state
from ayu_log import get as _get_logger
import ayu_host as host_module
from ayu_host import WallpaperHost
from ayu_overrides import Overrides

SCREEN_CHAT = "chat"
SCREEN_DIALOGS = "dialogs"
SCREEN_OTHER = "other"

_log = _get_logger("wallpaper.service")


def _dialog_id_of(activity: Any) -> Optional[int]:
    """Best-effort dialog id of an open chat."""
    for attribute in ("dialog_id", "dialogId"):
        try:
            value = getattr(activity, attribute)
            if value is not None:
                return int(value)
        except Exception:
            pass
    for field_name in ("dialog_id",):
        try:
            from hook_utils import get_private_field  # type: ignore

            value = get_private_field(activity, field_name)
            if value is not None:
                return int(value)
        except Exception:
            pass
    getter = getattr(activity, "getDialogId", None)
    if getter is not None:
        try:
            return int(getter())
        except Exception:
            pass
    return None


class WallpaperService:
    def __init__(self, prefs_obj: prefs.Prefs) -> None:
        self.prefs = prefs_obj
        self.overrides = Overrides()
        self._hosts: Dict[str, WallpaperHost] = {}
        self._local_path: Optional[str] = None
        self._local_error: str = ""
        self._kind = prefs.KIND_GRADIENT
        self._theme_fallback = 0xFF101014

    # -- configuration ------------------------------------------------------
    def load(self) -> None:
        with _log.timed("wallpaper service load", level_value=4):
            self.overrides.load()
            _log.debug("chat overrides loaded: %d", self.overrides.count())
            self._prune_cache()
            self.refresh()

    def _prune_cache(self) -> None:
        try:
            files.prune_cache()
        except Exception:
            pass

    def refresh(self) -> None:
        """Re-resolve the source and rebuild every attached host."""
        self._local_path, self._local_error = assets.resolve_local(self.prefs)
        if self._local_error:
            state.note_error(self._local_error)
        else:
            state.clear_error()
        self._kind = self._resolve_kind(None)
        self._theme_fallback = _fallback_color()
        _log.info(
            "source refreshed: %s, kind=%s, local=%s",
            self.describe_source(),
            self._kind,
            "yes" if self._local_path else "no",
        )
        if self._local_error:
            _log.warning("source error: %s", self._local_error)
        for key in list(self._hosts.keys()):
            self._rebuild(key)

    def _rebuild(self, key: str) -> None:
        host = self._hosts.get(key)
        if host is None:
            return
        if not self.prefs.bool("wallpaper_enabled"):
            host.detach()
            self._hosts.pop(key, None)
            return
        host.detach()
        host.kind = self._resolve_kind(host.dialog_id)
        host.local_path = self._local_path
        host._fallback_color = self._theme_fallback
        host.build()
        host.attach(host.width or 1080, host.height or 1920)

    # -- resolution ---------------------------------------------------------
    def enabled_for(self, screen: str) -> bool:
        if not self.prefs.bool("wallpaper_enabled"):
            return False
        if screen == SCREEN_CHAT:
            return self.prefs.bool("wallpaper_apply_chat")
        if screen == SCREEN_DIALOGS:
            return self.prefs.bool("wallpaper_apply_dialogs")
        return self.prefs.bool("wallpaper_apply_everywhere")

    def _resolve_kind(self, dialog_id: Optional[int]) -> str:
        override = self.overrides.get(dialog_id) if dialog_id is not None else None
        if override:
            forced = str(override.get("kind") or "")
            if forced in (prefs.KIND_GRADIENT, prefs.KIND_PARALLAX, prefs.KIND_PARTICLES, prefs.KIND_VIDEO):
                return forced
        chosen = self.prefs.text("wallpaper_kind")
        if chosen == prefs.KIND_PARALLAX and not self._local_path:
            # Nothing to parallax: fall back to the procedural renderer.
            return prefs.KIND_GRADIENT
        if chosen == prefs.KIND_VIDEO:
            if not self._local_path or not assets.is_video(self._local_path):
                return prefs.KIND_PARTICLES if self.prefs.int("particles_count") else prefs.KIND_GRADIENT
        if chosen == prefs.KIND_GRADIENT and self._local_path and assets.is_image(self._local_path):
            # A picture is selected: show it unless the user forced a kind.
            return prefs.KIND_PARALLAX
        return chosen or prefs.KIND_GRADIENT

    def current_kind(self) -> str:
        return self._kind

    def local_path(self) -> Optional[str]:
        return self._local_path

    def last_error(self) -> str:
        return self._local_error

    def describe_source(self) -> str:
        return assets.describe_source(self.prefs, self._local_path)

    # -- hosts --------------------------------------------------------------
    def host_for(self, screen: str, dialog_id: Optional[int]) -> WallpaperHost:
        key = "%s:%s" % (screen, dialog_id if dialog_id is not None else "-")
        host = self._hosts.get(key)
        if host is None:
            _log.debug("new host for %s (kind=%s)", key, self._resolve_kind(dialog_id))
            kind = self._resolve_kind(dialog_id)
            host = WallpaperHost(self.prefs, kind, self._local_path)
            host.dialog_id = dialog_id  # type: ignore[attr-defined]
            host.screen = screen  # type: ignore[attr-defined]
            host._fallback_color = self._theme_fallback
            host.build()
            self._hosts[key] = host
        elif host.renderer is None:
            host.build()
        return host

    def detach_key(self, key: str) -> None:
        host = self._hosts.pop(key, None)
        if host is not None:
            host.detach()

    def detach_all(self) -> None:
        if self._hosts:
            _log.info("detaching %d host(s)", len(self._hosts))
        for key in list(self._hosts.keys()):
            self.detach_key(key)
        engine.scheduler.stop_all()

    def active_hosts(self) -> int:
        return len(self._hosts)

    def notice_interaction(self) -> None:
        engine.scheduler.note_interaction()

    def feed_scroll(self, cell: Any) -> None:
        """Feed the message position into the parallax renderer, cheaply."""
        chat_key = None
        for key, host in self._hosts.items():
            if key.startswith(SCREEN_CHAT):
                chat_key = key
                break
        if chat_key is None:
            return
        host = self._hosts.get(chat_key)
        if host is None or host.renderer is None:
            return
        if not hasattr(host.renderer, "set_scroll_progress"):
            return
        try:
            top = float(cell.getTop())
            height = float(cell.getHeight()) or 1.0
            index = float(getattr(cell, "messageObject", None) and 0 or 0)
            host.renderer.set_scroll_progress(top + height * index)
        except Exception:
            pass

    def set_scrolling(self, scrolling: bool) -> None:
        if not self.prefs.bool("perf_pause_scroll"):
            engine.scheduler.set_global_pause(False)
            return
        engine.scheduler.set_global_pause(bool(scrolling))

    def apply_performance(self) -> None:
        eco = self.prefs.bool("perf_eco")
        fps = 30 if eco else self.prefs.int("perf_fps")
        engine.scheduler.configure(
            fps_limit=fps,
            idle_enabled=self.prefs.bool("perf_pause_idle"),
            idle_delay=self.prefs.int("perf_idle_delay"),
            background_pause=self.prefs.bool("perf_pause_background"),
        )

    # -- per-chat helpers ---------------------------------------------------
    def assign_override(self, dialog_id: int, data: Dict[str, Any]) -> bool:
        ok = self.overrides.set(dialog_id, data)
        _log.info("override for chat %s: %s (saved=%s)", dialog_id, data.get("kind"), ok)
        key = "%s:%s" % (SCREEN_CHAT, dialog_id)
        if key in self._hosts:
            self._rebuild(key)
        return ok

    def clear_override(self, dialog_id: int) -> bool:
        ok = self.overrides.clear(dialog_id)
        _log.info("override cleared for chat %s (saved=%s)", dialog_id, ok)
        key = "%s:%s" % (SCREEN_CHAT, dialog_id)
        if key in self._hosts:
            self._rebuild(key)
        return ok

    def clear_all_overrides(self) -> bool:
        ok = self.overrides.clear_all()
        for key in [entry for entry in self._hosts if entry.startswith(SCREEN_CHAT)]:
            self._rebuild(key)
        return ok


def _fallback_color() -> int:
    try:
        import ayu_theme as theme

        value = theme.current("key_windowBackgroundWhite", 0xFF101014)
        return value or 0xFF101014
    except Exception:
        return 0xFF101014
