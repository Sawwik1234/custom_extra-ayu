"""Attaching animated backgrounds to client screens.

Every entry point is optional: the attach module probes the client once, records
what it found in ``core.state.hooks`` and works with whatever is present. The
plugin never assumes a specific build.

Three installation strategies are tried in order:

1. **content view swap** — clone the screen's ``FrameLayout``, put the background
   view below the original children and install the clone. Works for both
   painted renderers and the video ``SurfaceView``.
2. **background drawable** — set our ``Drawable`` on the chat background view.
3. **decor background** — last resort, the window decor view.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core import compat, javabridge, state
from core.log import get as _get_logger
from wallpaper import host as host_module
from wallpaper.service import SCREEN_CHAT, SCREEN_DIALOGS, SCREEN_OTHER, WallpaperService

HOOK_CHAT = "ChatActivity"
HOOK_DIALOGS = "DialogsActivity"
HOOK_CELL = "ChatMessageCell"
HOOK_SCROLL = "RecyclerListView"
HOOK_THEME = "Theme"

_log = _get_logger("wallpaper.attach")


def probe() -> Dict[str, bool]:
    """Check which client internals are reachable. Cheap, runs once."""
    result = {
        HOOK_CHAT: javabridge.has("ChatActivity"),
        HOOK_DIALOGS: javabridge.has("DialogsActivity"),
        HOOK_CELL: javabridge.has("ChatMessageCell"),
        HOOK_SCROLL: javabridge.find_class("org.telegram.ui.Components.RecyclerListView") is not None,
        HOOK_THEME: javabridge.has("Theme"),
    }
    state.hooks.update(result)
    _log.info(
        "probe: %s",
        ", ".join("%s=%s" % (name, "ok" if bound else "no") for name, bound in sorted(result.items())),
    )
    return result


class AttachManager:
    def __init__(self, service: WallpaperService) -> None:
        self.service = service
        self._unhooks: Dict[str, Any] = {}
        self._installed: Dict[str, Any] = {}
        self._bound = False

    # -- installation -------------------------------------------------------
    def install(self) -> None:
        probe()
        if not compat.supported():
            _note("android %s is below the supported minimum" % compat.summary())
        self._bind_chat_activity()
        self._bind_dialogs_activity()
        self._bind_cell()
        self._bind_scroll()
        self.bind_everywhere()
        self._bound = True

    def uninstall(self) -> None:
        for name in list(self._unhooks.keys()):
            handle = self._unhooks.pop(name, None)
            if handle is None:
                continue
            try:
                if hasattr(handle, "unhook"):
                    handle.unhook()
            except Exception:
                pass
        self._installed.clear()
        self._bound = False

    # -- chat screen --------------------------------------------------------
    def _bind_chat_activity(self) -> None:
        activity = javabridge.cls("ChatActivity")
        plugin = _plugin_ref()
        if activity is None or plugin is None:
            javabridge.mark(HOOK_CHAT, False)
            return
        try:
            method = activity.getDeclaredMethod("createView")
            method.setAccessible(True)
        except Exception as error:
            _note("ChatActivity.createView not found: %s" % error)
            javabridge.mark(HOOK_CHAT, False)
            return

        manager = self

        def before(param: Any) -> None:
            _count()

        def after(param: Any) -> None:
            try:
                manager.on_chat_view_ready(param.thisObject)
            except Exception as error:
                _note("chat attach failed: %s" % error)

        try:
            handle = plugin.hook_method(method, before=before, after=after)
            self._unhooks[HOOK_CHAT] = handle
            javabridge.mark(HOOK_CHAT, bool(handle))
        except Exception as error:
            _note("ChatActivity hook failed: %s" % error)
            javabridge.mark(HOOK_CHAT, False)

        self._bind_chat_destroy(activity, plugin)

    def _bind_chat_destroy(self, activity: Any, plugin: Any) -> None:
        """Release the host when the chat is closed, so nothing keeps drawing."""
        manager = self
        for name in ("onFragmentDestroy", "onDestroy"):
            try:
                method = activity.getDeclaredMethod(name)
                method.setAccessible(True)
            except Exception:
                continue

            def before(param: Any) -> None:
                try:
                    dialog_id = _dialog_id_of(param.thisObject)
                except Exception:
                    dialog_id = None
                manager.service.detach_key("chat:%s" % dialog_id)
                manager._installed.pop("chat:%s" % dialog_id, None)

            try:
                plugin.hook_method(method, before=before)
                return
            except Exception:
                continue

    def on_chat_view_ready(self, activity: Any) -> None:
        if not self.service.enabled_for(SCREEN_CHAT):
            return
        dialog_id = _dialog_id_of(activity)
        host = self.service.host_for(SCREEN_CHAT, dialog_id)
        installed = self._install(activity, host, "chat:%s" % dialog_id)
        _log.debug(
            "chat %s: %s, kind=%s, installed=%s",
            dialog_id,
            "enabled" if installed else "attach failed",
            host.kind,
            installed,
        )

    # -- chat list ----------------------------------------------------------
    def _bind_dialogs_activity(self) -> None:
        activity = javabridge.cls("DialogsActivity")
        plugin = _plugin_ref()
        if activity is None or plugin is None:
            javabridge.mark(HOOK_DIALOGS, False)
            return
        try:
            method = activity.getDeclaredMethod("createView")
            method.setAccessible(True)
        except Exception as error:
            _note("DialogsActivity.createView not found: %s" % error)
            javabridge.mark(HOOK_DIALOGS, False)
            return

        manager = self

        def after(param: Any) -> None:
            try:
                manager.on_dialogs_view_ready(param.thisObject)
            except Exception as error:
                _note("dialogs attach failed: %s" % error)

        try:
            handle = plugin.hook_method(method, after=after)
            self._unhooks[HOOK_DIALOGS] = handle
            javabridge.mark(HOOK_DIALOGS, bool(handle))
        except Exception as error:
            _note("DialogsActivity hook failed: %s" % error)
            javabridge.mark(HOOK_DIALOGS, False)

    def on_dialogs_view_ready(self, activity: Any) -> None:
        if not self.service.enabled_for(SCREEN_DIALOGS):
            return
        host = self.service.host_for(SCREEN_DIALOGS, None)
        if self._install(activity, host, "dialogs"):
            _log.debug("chat list background installed (kind=%s)", host.kind)

    # -- other screens ------------------------------------------------------
    def bind_everywhere(self) -> None:
        """Paint the plugin background behind every screen of the app."""
        activity = javabridge.cls("LaunchActivity")
        plugin = _plugin_ref()
        if activity is None or plugin is None:
            return
        service = self.service

        def after(param: Any) -> None:
            if not service.enabled_for(SCREEN_OTHER):
                return
            host = service.host_for(SCREEN_OTHER, None)
            peer = host_module.build_drawable(host)
            if peer is None:
                return
            java_object = getattr(peer, "java", None)
            if java_object is None:
                return
            host.drawable_peer = peer
            try:
                decor = param.thisObject.getWindow().getDecorView()
                decor.setBackground(java_object)
            except Exception as error:
                _note("everywhere attach failed: %s" % error)

        for name in ("onCreate", "onResume"):
            try:
                from android.os import Bundle  # type: ignore

                method = activity.getDeclaredMethod(name, Bundle)
                method.setAccessible(True)
            except Exception:
                continue
            try:
                plugin.hook_method(method, after=after)
                return
            except Exception:
                continue

    # -- message cell -------------------------------------------------------
    def _bind_cell(self) -> None:
        cell = javabridge.cls("ChatMessageCell")
        plugin = _plugin_ref()
        if cell is None or plugin is None:
            javabridge.mark(HOOK_CELL, False)
            return
        canvas = javabridge.find_class("android.graphics.Canvas")
        if canvas is None:
            javabridge.mark(HOOK_CELL, False)
            return
        try:
            method = cell.getDeclaredMethod("onDraw", canvas)
            method.setAccessible(True)
        except Exception as error:
            _note("ChatMessageCell.onDraw not found: %s" % error)
            javabridge.mark(HOOK_CELL, False)
            return

        service = self.service

        def before(param: Any) -> None:
            _count()
            service.notice_interaction()
            service.feed_scroll(param.thisObject)

        try:
            handle = plugin.hook_method(method, before=before)
            self._unhooks[HOOK_CELL] = handle
            javabridge.mark(HOOK_CELL, bool(handle))
        except Exception as error:
            _note("ChatMessageCell hook failed: %s" % error)
            javabridge.mark(HOOK_CELL, False)

    # -- scroll -------------------------------------------------------------
    def _bind_scroll(self) -> None:
        list_class = javabridge.find_class("org.telegram.ui.Components.RecyclerListView")
        plugin = _plugin_ref()
        if list_class is None or plugin is None:
            javabridge.mark(HOOK_SCROLL, False)
            return
        try:
            from java.lang import Integer  # type: ignore

            method = list_class.getDeclaredMethod("onScrolled", Integer.TYPE, Integer.TYPE)
        except Exception:
            try:
                int_class = javabridge.find_class("int")
                method = list_class.getDeclaredMethod("onScrolled", int_class, int_class)
            except Exception as error:
                _note("onScrolled not found: %s" % error)
                javabridge.mark(HOOK_SCROLL, False)
                return

        service = self.service

        def before(param: Any) -> None:
            try:
                dy = int(param.args[1])
            except Exception:
                return
            if abs(dy) > 2:
                service.set_scrolling(True)
                service.notice_interaction()

        def after(param: Any) -> None:
            service.set_scrolling(False)

        try:
            handle = plugin.hook_method(method, before=before, after=after)
            self._unhooks[HOOK_SCROLL] = handle
            javabridge.mark(HOOK_SCROLL, bool(handle))
        except Exception as error:
            _note("scroll hook failed: %s" % error)
            javabridge.mark(HOOK_SCROLL, False)

    # -- installation strategies -------------------------------------------
    def _install(self, activity: Any, host: Any, key: str) -> bool:
        if self._installed.get(key) is not None:
            # Already installed on this screen: refresh the renderer instead.
            self._refresh(host)
            return True

        from android_utils import run_on_ui_thread  # type: ignore

        result: Dict[str, bool] = {}

        def work() -> None:
            result["ok"] = self._install_sync(activity, host, key)

        try:
            run_on_ui_thread(work)
        except Exception:
            result["ok"] = self._install_sync(activity, host, key)
        return bool(result.get("ok"))

    def _install_sync(self, activity: Any, host: Any, key: str) -> bool:
        with _log.timed("attach %s" % key):
            return self._install_steps(activity, host, key)

    def _install_steps(self, activity: Any, host: Any, key: str) -> bool:
        fade = self.service.prefs.bool("wallpaper_fade")
        duration = self.service.prefs.int("wallpaper_fade_duration")

        content = _content_view(activity)
        if content is not None:
            view = host.create_view(content.getContext())
            if view is not None:
                width, height = _size_of(content)
                host.attach(width, height)
                if _insert_behind(content, view):
                    self._installed[key] = view
                    _log.debug("background view inserted behind %s (%dx%d)", key, width, height)
                    if fade and duration > 0:
                        _fade_in(view, duration)
                    return True

        # Painted fallback: install the drawable directly.
        peer = host_module.build_drawable(host)
        if peer is None:
            return False
        java_object = getattr(peer, "java", None)
        if java_object is None:
            return False
        host.drawable_peer = peer
        host.attach(host.width or 1080, host.height or 1920)
        if _install_drawable(activity, java_object):
            self._installed[key] = java_object
            _log.debug("background drawable installed for %s", key)
            return True
        _log.once("install-failed-%s" % key, "no attach point found for %s", key)
        return False

    def _refresh(self, host: Any) -> None:
        try:
            host.attach(host.width or 1080, host.height or 1920)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _content_view(activity: Any) -> Optional[Any]:
    try:
        return activity.getWindow().getDecorView()
    except Exception:
        return None


def _size_of(view: Any) -> tuple:
    try:
        width = int(view.getWidth())
        height = int(view.getHeight())
        if width > 0 and height > 0:
            return (width, height)
    except Exception:
        pass


    try:
        metrics = view.getResources().getDisplayMetrics()
        return (int(metrics.widthPixels), int(metrics.heightPixels))
    except Exception:
        return (1080, 1920)


def _insert_behind(content: Any, view: Any) -> bool:
    """Put ``view`` below the first child of a ``FrameLayout`` content view."""
    try:
        from android.view import ViewGroup  # type: ignore

        layout_params = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
        view.setLayoutParams(layout_params)
        content.addView(view, 0)
        return True
    except Exception as error:
        _note("cannot insert background view: %s" % error)
        return False


def _fade_in(view: Any, duration: int) -> None:
    try:
        view.setAlpha(0.0)
        view.animate().alpha(1.0).setDuration(int(duration)).start()
    except Exception:
        try:
            view.setAlpha(1.0)
        except Exception:
            pass


def _install_drawable(activity: Any, drawable: Any) -> bool:
    for name in ("chatBackgroundView", "backgroundView", "listView"):
        try:
            from hook_utils import get_private_field  # type: ignore

            target = get_private_field(activity, name)
        except Exception:
            target = None
        if target is not None and _set_background(target, drawable):
            return True
    try:
        decor = activity.getWindow().getDecorView()
        return _set_background(decor, drawable)
    except Exception:
        return False


def _set_background(target: Any, drawable: Any) -> bool:
    try:
        target.setBackground(drawable)
        return True
    except Exception:
        return False


def _dialog_id_of(activity: Any) -> Optional[int]:
    for attribute in ("dialog_id", "dialogId"):
        try:
            value = getattr(activity, attribute)
            if value is not None:
                return int(value)
        except Exception:
            pass
    try:
        from hook_utils import get_private_field  # type: ignore

        value = get_private_field(activity, "dialog_id")
        if value is not None:
            return int(value)
    except Exception:
        pass
    return None


_plugin = None


def set_plugin(plugin: Any) -> None:
    global _plugin
    _plugin = plugin


def _plugin_ref() -> Any:
    return _plugin


def _count() -> None:
    state.count_hook_event()


def _note(message: str) -> None:
    state.note_error(message)
    _log.warning(message)
