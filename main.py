"""Custom Extra Ayu — live wallpapers, themes and skins for exteraGram.

Author: @sawwik1234

The entry module only wires things together; every feature is a flat module in
this same directory (``ayu_wallpaper.py``, ``ayu_skins.py``, ...).

Flat modules are a hard requirement, not a style choice. Elyx resolves plugin
imports against the plugin root, but it builds packages with
``importlib.util.spec_from_loader(..., is_package=True)``, which leaves
``__path__`` empty: ``import core`` succeeds while ``import core.assets`` raises
``ImportError`` ("unknown location"). Subdirectories can therefore never be
imported from a plugin here, so the code stays flat and modules that would have
formed a package use an ``ayu_<area>_<name>`` prefix instead.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from base_plugin import (
    AppEvent,
    BasePlugin,
    HookResult,
    HookStrategy,
    MenuItemData,
    MenuItemType,
)  # type: ignore

import ayu_assets as assets
import ayu_compat as compat
import ayu_engine as engine
import ayu_files as files
import ayu_javabridge as javabridge
import ayu_log as log_module
import ayu_meta as meta
import ayu_prefs as prefs_module
import ayu_state as state
import ayu_theme as theme
import ayu_i18n as i18n
from ayu_i18n import t
import ayu_skin_apply as skins_apply
import ayu_skins as skins_registry
import ayu_themes as themes_model
import ayu_compose as compose
from ayu_bulletin import bulletin_error, bulletin_info, bulletin_success, clipboard
from ayu_dialogs import dialog_choose
from ayu_pages import Pages
from ayu_log import get as _get_logger
import ayu_attach as attach_module
from ayu_wallpaper import WallpaperService


_log = _get_logger("main")


def _dialog_title(context: Optional[Dict[str, Any]]) -> str:
    if not context:
        return "chat"
    for key in ("dialog_id", "dialogId", "chatId", "userId"):
        value = context.get(key)
        if value is not None:
            return str(value)
    chat = context.get("chat")
    if chat is not None:
        try:
            return str(chat.id)
        except Exception:
            pass
    return "chat"


class CustomExtraAyuPlugin(BasePlugin):
    """Entry point of the plugin.

    Never shadow a name owned by the base class. The workload here is
    ``BasePlugin.__init__``: it assigns ``self.version = ''`` (as do ``name``,
    ``author``, ``description``, ``icon``, ``enabled``, ``initialized``). A
    ``version`` property on the subclass turns that assignment into
    ``AttributeError: property 'version' ... has no setter`` **inside
    __init__**, before any plugin code runs, so the whole plugin fails to
    construct.

    Metadata therefore lives in ``ayu_meta`` and is exposed under distinct
    names (``plugin_name`` / ``plugin_version``), which keeps working whether
    the host's BasePlugin defines ``version`` or not — the two SDK generations
    disagree on that, and a fixed attribute name is the only common ground.
    """

    @property
    def plugin_name(self) -> str:
        return meta.name()

    @property
    def plugin_version(self) -> str:
        return meta.version()

    # -- lifecycle ----------------------------------------------------------
    def on_plugin_load(self) -> None:
        i18n.init()
        log_module.bind(self.logger)
        self._apply_log_level()
        _log.info("bootstrap: log level %s, buffer %d", log_module.stats()["level"], log_module.count())

        with _log.timed("files.init"):
            files.init()
        self.prefs = prefs_module.Prefs(self)
        state.clear_error()

        with _log.timed("wallpaper service"):
            self.wallpaper = WallpaperService(self.prefs)
        self.skins = skins_registry.Registry()
        self.pages = Pages(self)

        self._menu_ids: List[str] = []
        self._await_import: Optional[str] = None
        self._await_picked_file = False
        self._pending_theme_index: int = -1

        with _log.timed("wallpaper load"):
            self.wallpaper.load()
        self.apply_performance()
        with _log.timed("attach install"):
            self._install_attach()
        self._bind_file_picker()
        self._register_menu_items()
        self._register_send_hook()
        with _log.timed("skins apply"):
            self.apply_skins()
        self._reapply_theme()

        _log.info(
            "loaded %s v%s | wallpaper=%s kind=%s source=%s | skins=%s | android API %d",
            self.plugin_name,
            self.plugin_version,
            self.prefs.bool("wallpaper_enabled"),
            self.wallpaper.current_kind(),
            self.wallpaper.describe_source(),
            self.prefs.bool("skins_enabled"),
            compat.android_version(),
        )
        _log.debug("hook bindings: %s", javabridge.bindings())

    def on_plugin_unload(self) -> None:
        _log.info("unloading, %d log record(s) buffered", log_module.count())
        try:
            engine.shutdown()
        except Exception:
            pass
        try:
            if getattr(self, "wallpaper", None) is not None:
                self.wallpaper.detach_all()
        except Exception:
            pass
        try:
            if getattr(self, "skins", None) is not None:
                self.skins.release()
        except Exception:
            pass
        try:
            theme.revert()
        except Exception:
            pass
        try:
            import ayu_images as images

            images.clear_cache()
        except Exception:
            pass
        try:
            if getattr(self, "_attach", None) is not None:
                self._attach.uninstall()
        except Exception:
            pass
        _log.info("unloaded cleanly")

    def on_app_event(self, event_type: AppEvent) -> None:
        scheduler = engine.scheduler
        if event_type == AppEvent.PAUSE:
            if self.prefs.bool("perf_pause_background"):
                scheduler.set_backgrounded(True)
        elif event_type == AppEvent.RESUME:
            scheduler.set_backgrounded(False)
            scheduler.resume()
        elif event_type == AppEvent.STOP:
            scheduler.set_backgrounded(True)
        elif event_type == AppEvent.START:
            scheduler.set_backgrounded(False)

    # -- settings -----------------------------------------------------------
    def create_settings(self) -> List[Any]:
        rows: List[Any] = []
        try:
            rows.extend(self.pages.page_wallpaper())
            rows.append(compose.divider())
            rows.extend(self.pages.page_themes())
            rows.append(compose.divider())
            rows.extend(self.pages.page_skins())
            rows.append(compose.divider())
            rows.extend(self.pages.page_per_chat())
            rows.append(compose.divider())
            rows.append(
                compose.action(
                    t("page_performance"),
                    None,
                    icon="msg_speed",
                    sub_page=self.pages.page_performance,
                )
            )
            rows.append(
                compose.action(
                    t("page_diagnostics"),
                    None,
                    icon="msg_info",
                    sub_page=self.pages.page_diagnostics,
                )
            )
        except Exception as error:
            state.note_error("settings build failed: %s" % error)
            _log.exception("settings build failed")
            rows = [compose.info("Custom Extra Ayu", str(error), red=True)]
        return rows

    # -- install ------------------------------------------------------------
    def _install_attach(self) -> None:
        self._attach = attach_module.AttachManager(self.wallpaper)
        attach_module.set_plugin(self)
        try:
            self._attach.install()
        except Exception:
            _log.exception("attach installation failed")

    def _bind_file_picker(self) -> None:
        """Watch the screen result callback to catch a file picked by the user."""
        self._await_picked_file = False
        try:
            activity = javabridge.cls("LaunchActivity")
            if activity is None:
                return
            int_class = javabridge.find_class("int")
            from android.content import Intent  # type: ignore

            method = activity.getDeclaredMethod("onActivityResult", int_class, int_class, Intent)
            method.setAccessible(True)
        except Exception as error:
            _log.debug("file picker hook unavailable: %s", error)
            return

        plugin = self

        def after(param: Any) -> None:
            import_kind = getattr(plugin, "_await_import", None)
            if import_kind:
                plugin._await_import = None
                try:
                    data = param.args[2]
                    uri = data.getData() if data is not None else None
                except Exception:
                    uri = None
                if uri is not None:
                    plugin.handle_import_uri(import_kind, uri)
                return

            if not getattr(plugin, "_await_picked_file", False):
                return
            try:
                data = param.args[2]
                if data is None:
                    return
                uri = data.getData()
                if uri is None:
                    return
            except Exception:
                return
            plugin._await_picked_file = False
            try:
                from client_utils import run_on_queue  # type: ignore
            except Exception:
                run_on_queue = None

            def copy() -> None:
                copied = files.copy_from_uri(uri, prefix="picked")
                if not copied:
                    bulletin_error(t("wallpaper_missing"))
                    return
                plugin._use_background_file(copied)

            if run_on_queue is not None:
                run_on_queue(copy)
            else:
                copy()

        try:
            self._picker_unhook = self.hook_method(method, after=after)
        except Exception as error:
            _log.debug("file picker hook failed: %s", error)

    def _register_menu_items(self) -> None:
        specs = (
            (MenuItemType.MESSAGE_CONTEXT_MENU, "wallpaper"),
            (MenuItemType.PROFILE_ACTION_MENU, "wallpaper"),
            (MenuItemType.CHAT_ACTION_MENU, "wallpaper"),
        )
        for menu_type, _kind in specs:
            try:
                item_id = self.add_menu_item(
                    MenuItemData(
                        menu_type=menu_type,
                        text=t("per_chat_dialog"),
                        on_click=self.on_wallpaper_menu_click,
                        icon="msg_photo",
                        priority=5,
                    )
                )
                if item_id:
                    self._menu_ids.append(item_id)
            except Exception:
                _log.warning("menu item %s unavailable", menu_type)

    def _register_send_hook(self) -> None:
        try:
            self.add_on_send_message_hook()
        except Exception:
            _log.warning("send-message hook unavailable")

    def on_send_message_hook(self, account: int, params: Any) -> HookResult:
        """`.ayu` prints a short status bulletin."""
        try:
            message = getattr(params, "message", None)
            if not isinstance(message, str):
                return HookResult()
            if message.strip() != ".ayu":
                return HookResult()
            state.count_hook_event()
            bulletin_info(self.status_line())
            return HookResult(strategy=HookStrategy.CANCEL)
        except Exception:
            return HookResult()

    def status_line(self) -> str:
        return "wallpaper: %s · %s · %s" % (
            t(self._state_key()),
            self.wallpaper.current_kind(),
            self.wallpaper.describe_source(),
        )

    # -- wallpaper callbacks ------------------------------------------------
    def on_wallpaper_changed(self) -> None:
        try:
            self.wallpaper.refresh()
            self.apply_performance()
        except Exception:
            _log.exception("wallpaper refresh failed")

    def on_url_entered(self, value: Any) -> None:
        url = str(value or "").strip()
        self.prefs.set("wallpaper_url", url)
        if not url:
            return
        self.prefs.set("wallpaper_source", prefs_module.SOURCE_URL)
        self.reload_background()

    def reload_background(self) -> None:
        from client_utils import run_on_queue  # type: ignore

        def work() -> None:
            path, error = assets.refresh_source(self.prefs, force_download=True)
            if error:
                state.note_error(error)
                bulletin_error(t("wallpaper_state_error", error=error))
                return
            files.prune_cache()
            self.wallpaper.refresh()
            bulletin_success(t("wallpaper_state_ok"))

        try:
            run_on_queue(work)
        except Exception:
            work()

    def pick_background_file(self) -> None:
        """Open the system file manager for an image, GIF or video."""
        opened = False
        try:
            from android.content import Intent  # type: ignore

            activity = javabridge.application_context()
            if activity is not None:
                intent = Intent(Intent.ACTION_GET_CONTENT)
                intent.setType("*/*")
                intent.addCategory(Intent.CATEGORY_OPENABLE)
                intent.putExtra(Intent.EXTRA_MIME_TYPES, _media_mime_types())
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                try:
                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                except Exception:
                    pass
                self._await_picked_file = True
                activity.startActivityForResult(intent, 4211)
                opened = True
        except Exception as error:
            _log.debug("file picker failed: %s", error)

        if not opened:
            self.scan_backgrounds_folder()

    def on_file_picked(self, path_value: str) -> None:
        """Called by the activity-result hook with the chosen file."""
        if not path_value:
            return
        self._await_picked_file = False
        self._use_background_file(path_value)

    def scan_backgrounds_folder(self) -> None:
        """Fallback chooser over files already dropped into the plugin folder."""
        folder = files.path("backgrounds")
        files.ensure(folder)
        found = files.list_files(folder, ("png", "jpg", "jpeg", "webp", "mp4", "webm", "gif", "mkv", "bmp"))
        if not found:
            clipboard(folder)
            bulletin_info("%s\n%s" % (t("wallpaper_pick_file_sub"), folder))
            return
        names = sorted(found.keys())
        dialog_choose(
            t("wallpaper_pick_file"),
            names,
            lambda index: self._use_background_file(found[names[index]]),
        )

    def _use_background_file(self, source_path: str) -> None:
        copied = assets.adopt_picked_file(source_path)
        if not copied:
            bulletin_error(t("wallpaper_missing"))
            return
        self.prefs.set("wallpaper_file", copied)
        self.prefs.set("wallpaper_source", prefs_module.SOURCE_FILE)
        self.on_wallpaper_changed()
        bulletin_success(t("wallpaper_state_ok"))

    # -- theme callbacks ----------------------------------------------------
    def on_theme_changed(self) -> None:
        if self.prefs.bool("wallpaper_enabled"):
            self.wallpaper.refresh()

    def apply_theme_by_index(self, index: Any) -> None:
        themes = themes_model.load_all()
        try:
            position = int(index)
        except (TypeError, ValueError):
            return
        if not (0 <= position < len(themes)):
            return
        item = themes[position]
        self.prefs.set("theme_active", str(item.get("name")))
        for field in ("accent", "out_bubble", "in_bubble", "header_color", "page_color"):
            self.prefs.set("theme_" + field, str(item.get(field)))
        self.prefs.set("theme_bubbles_alpha", int(item.get("bubbles_alpha", 100)))
        self.apply_current_theme()

    def preview_theme(self, index: int) -> None:
        themes = themes_model.load_all()
        if not (0 <= index < len(themes)):
            return
        item = themes[index]
        warning = themes_model.readability_warning(item)
        bulletin_info("%s: %s" % (item.get("name"), warning or item.get("accent")))

    def create_theme_from_current(self) -> None:
        snapshot = themes_model.read_current_look()
        name = t("theme_new_name") + " " + str(int(state.hook_events) + 1)
        item = themes_model.create(name, snapshot)
        themes = themes_model.load_all()
        themes.append(item)
        if themes_model.save_all(themes):
            self.prefs.set("theme_active", name)
            bulletin_success(t("theme_saved"))
        else:
            bulletin_error("cannot write theme file")

    def apply_current_theme(self) -> None:
        item = self._current_theme_data()
        if item is None:
            bulletin_error(t("theme_list_empty"))
            return
        applied = themes_model.apply(item)
        if applied:
            bulletin_success(t("theme_saved"))
        else:
            bulletin_error(t("diag_fail"))
        self.on_theme_changed()

    def reset_theme(self) -> None:
        theme.revert()
        bulletin_info(t("theme_reset_done"))

    def delete_active_theme(self) -> None:
        name = self.prefs.text("theme_active")
        themes = themes_model.load_all()
        index = themes_model.find_index(themes, name)
        if index < 0:
            return
        themes = themes_model.remove(themes, index)
        themes_model.save_all(themes)
        self.prefs.set("theme_active", "")
        bulletin_info(t("theme_deleted"))

    def _current_theme_data(self) -> Optional[Dict[str, Any]]:
        name = self.prefs.text("theme_active")
        if name:
            for item in themes_model.load_all():
                if item.get("name") == name:
                    return item
        return {
            "name": name or "custom",
            "accent": self.prefs.text("theme_accent"),
            "out_bubble": self.prefs.text("theme_out_bubble"),
            "in_bubble": self.prefs.text("theme_in_bubble"),
            "header_color": self.prefs.text("theme_header_color"),
            "page_color": self.prefs.text("theme_page_color"),
            "bubbles_alpha": self.prefs.int("theme_bubbles_alpha"),
        }

    def _reapply_theme(self) -> None:
        if not self.prefs.text("theme_active"):
            return
        try:
            item = self._current_theme_data()
            if item is not None:
                themes_model.apply(item)
        except Exception:
            _log.exception("theme reapply failed")

    # -- skin callbacks -----------------------------------------------------
    def apply_skins(self, force_reload: bool = False) -> None:
        try:
            if not self.prefs.bool("skins_enabled"):
                skins_apply.release()
                if getattr(self, "skins", None) is not None:
                    self.skins.deactivate()
                return
            skin_id = self.prefs.text("skin_active") or self.skins.ensure_default()
            if force_reload or self.skins.current() is None or (self.skins.current() and self.skins.current().skin_id != skin_id):
                self.skins.activate(skin_id)
            skin = self.skins.current()
            mode = skins_apply.resolved_mode(self.prefs)
            if mode == "texture":
                skins_apply.apply_textures(skin, self.prefs)
            skins_apply.apply_tints(skin, self.prefs)
            self.on_theme_changed()
        except Exception:
            _log.exception("skin apply failed")

    def activate_skin(self, index: Any, folders: List[str]) -> None:
        try:
            position = int(index)
        except (TypeError, ValueError):
            return
        if not (0 <= position < len(folders)):
            return
        self.prefs.set("skin_active", folders[position])
        self.apply_skins(force_reload=True)

    def create_default_skin(self) -> None:
        skin_id = self.skins.ensure_default()
        self.prefs.set("skin_active", skin_id)
        self.prefs.set("skins_enabled", True)
        bulletin_info(os.path.join(files.skins_dir(), skin_id))
        self.apply_skins(force_reload=True)

    # -- imports ------------------------------------------------------------
    def import_skin_archive(self) -> None:
        """Import a skin manifest (JSON) and copy its images next to it."""
        self._open_import("skin")

    def import_theme_archive(self) -> None:
        """Import a theme JSON file into the theme list."""
        self._open_import("theme")

    def _open_import(self, kind: str) -> None:
        try:
            from android.content import Intent  # type: ignore

            context = javabridge.application_context()
            if context is None:
                bulletin_error("no activity")
                return
            intent = Intent(Intent.ACTION_GET_CONTENT)
            intent.setType("application/json")
            intent.addCategory(Intent.CATEGORY_OPENABLE)
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            try:
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            except Exception:
                pass
            self._await_import = kind
            context.startActivityForResult(intent, 4212 if kind == "skin" else 4213)
        except Exception:
            _log.exception("import dialog failed")
            bulletin_error("cannot open file picker")

    def handle_import_uri(self, kind: str, uri: Any) -> None:
        copied = files.copy_from_uri(uri, prefix="import")
        if not copied:
            bulletin_error(t("wallpaper_missing"))
            return
        if kind == "theme":
            self._import_theme_file(copied)
        else:
            self._import_skin_file(copied)

    def _import_theme_file(self, path_value: str) -> None:
        import json

        raw = files.read_file(path_value)
        if not raw:
            bulletin_error("empty file")
            return
        try:
            data = json.loads(raw)
        except Exception:
            bulletin_error("invalid json")
            return
        candidates = data.get("themes") if isinstance(data, dict) and "themes" in data else [data]
        if isinstance(candidates, dict):
            candidates = [candidates]
        themes = themes_model.load_all()
        added = 0
        for item in candidates or []:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            themes.append(themes_model.create(str(item.get("name")), item))
            added += 1
        if added and themes_model.save_all(themes):
            bulletin_success("%s: %d" % (t("theme_import"), added))
        else:
            bulletin_error(t("theme_invalid_color"))

    def _import_skin_file(self, path_value: str) -> None:
        import json

        raw = files.read_file(path_value)
        if not raw:
            bulletin_error("empty file")
            return
        try:
            payload = json.loads(raw)
        except Exception:
            bulletin_error("invalid json")
            return
        skin_id = str(payload.get("id") or payload.get("name") or "imported").lower().replace(" ", "_")
        skin_id = "".join(ch for ch in skin_id if ch.isalnum() or ch in "_-") or "imported"
        target_folder = os.path.join(files.skins_dir(), skin_id)
        files.ensure(target_folder)
        files.write_json(os.path.join(skin_id, "skin.json"), payload)
        self.prefs.set("skin_active", skin_id)
        self.prefs.set("skins_enabled", True)
        bulletin_success(os.path.join(files.skins_dir(), skin_id))
        self.apply_skins(force_reload=True)

    # -- per-chat callbacks -------------------------------------------------
    def on_wallpaper_menu_click(self, context: Dict[str, Any]) -> None:
        dialog_id = self._dialog_id(context)
        if dialog_id is None:
            bulletin_error("no chat in context")
            return
        options = [t("per_chat_inherit")] + [t(label) for _key, label in self._kind_options()]
        dialog_choose(
            t("per_chat_dialog"),
            options,
            lambda index: self._apply_chat_choice(dialog_id, index),
        )

    def _apply_chat_choice(self, dialog_id: int, index: int) -> None:
        if index == 0:
            self.wallpaper.clear_override(dialog_id)
            bulletin_info(t("per_chat_cleared"))
            return
        kinds = [key for key, _label in self._kind_options()]
        kind = kinds[index - 1] if index - 1 < len(kinds) else prefs_module.KIND_GRADIENT
        ok = self.wallpaper.assign_override(dialog_id, {"kind": kind, "source": self.wallpaper.describe_source()})
        if ok:
            bulletin_success(t("per_chat_saved"))
        else:
            bulletin_error("cannot save override")

    def clear_chat_override(self, dialog_key: Any) -> None:
        try:
            dialog_id = int(str(dialog_key))
        except (TypeError, ValueError):
            return
        self.wallpaper.clear_override(dialog_id)
        bulletin_info(t("per_chat_cleared"))

    def clear_all_chat_overrides(self) -> None:
        self.wallpaper.clear_all_overrides()
        bulletin_info(t("per_chat_cleared"))

    def _kind_options(self):
        return (
            (prefs_module.KIND_GRADIENT, "kind_gradient"),
            (prefs_module.KIND_PARALLAX, "kind_parallax"),
            (prefs_module.KIND_PARTICLES, "kind_particles"),
            (prefs_module.KIND_VIDEO, "kind_video"),
        )

    def _dialog_id(self, context: Optional[Dict[str, Any]]) -> Optional[int]:
        if not context:
            return None
        for key in ("dialog_id", "dialogId"):
            value = context.get(key)
            if value is not None:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    pass
        return None

    # -- performance --------------------------------------------------------
    def apply_performance(self) -> None:
        try:
            self.wallpaper.apply_performance()
        except Exception:
            _log.exception("performance apply failed")

    # -- diagnostics --------------------------------------------------------
    def client_version(self) -> str:
        try:
            from client_utils import get_user_config  # type: ignore

            user_config = get_user_config()
            value = getattr(user_config, "clientVersion", None)
            if value:
                return str(value)
        except Exception:
            pass
        try:
            config = javabridge.cls("ExteraConfig")
            if config is not None:
                return str(getattr(config, "getVersion", lambda: "")() or "")
        except Exception:
            pass
        return "unknown"

    def android_release(self) -> str:
        try:
            from android.os import Build  # type: ignore

            return str(Build.VERSION.RELEASE)
        except Exception:
            return "unknown"

    def plugin_sdk_version(self) -> str:
        """Host SDK version.

        Elyx plugins have no ``sdk_version`` attribute — it was a single-file
        plugin constant. The runtime exposes the value in ``_sdk_version`` and
        the plugin only *requires* a minimum in ``metainfo.yml``.
        """
        try:
            import _sdk_version  # type: ignore

            value = getattr(_sdk_version, "__version__", None)
            if isinstance(value, str) and value:
                return value
        except Exception:
            pass
        for attribute in ("sdk_version", "sdkVersion"):
            try:
                value = getattr(self, attribute, None)
                if isinstance(value, str) and value:
                    return value
            except Exception:
                continue
        return meta.sdk_requirement() or "unknown"

    def set_debug(self, value: Any) -> None:
        enabled = bool(value)
        self.prefs.set("diag_debug", enabled)
        self._apply_log_level()

    def _apply_log_level(self) -> None:
        """Debug switch on the diagnostics page drives both loggers."""
        debug = False
        try:
            debug = self.prefs.bool("diag_debug")
        except Exception:
            debug = False
        log_module.set_level("debug" if debug else "info")
        _log.info("log level set to %s", "debug" if debug else "info")

    def copy_log(self) -> None:
        """Copy environment plus the real recent log lines."""
        header = [
            "=== Custom Extra Ayu ===",
            "build: %s" % self.plugin_version,
            "client: %s · android %s (API %d)" % (
                self.client_version(),
                self.android_release(),
                compat.android_version(),
            ),
            "wallpaper: %s / %s / %s" % (
                self._state_key(),
                self.wallpaper.current_kind(),
                self.wallpaper.describe_source(),
            ),
            "skins: %s / %s" % (self.prefs.bool("skins_enabled"), state.skin_source or "-"),
            "hooks: %s" % javabridge.bindings(),
            "events: %d" % state.hook_events,
            "log: %s" % log_module.stats(),
            "=== log ===",
        ]
        body = log_module.recent(limit=150)
        text = "\n".join(header + [body or "(empty)"])
        clipboard(text)
        _log.info("log copied (%d chars)", len(text))
        bulletin_info(t("diag_copied"))

    def reset_everything(self) -> None:
        try:
            theme.revert()
        except Exception:
            pass
        self.prefs.reset_all()
        self.apply_performance()
        self.on_wallpaper_changed()
        bulletin_info(t("diag_reset_done"))

    def _log_summary(self) -> str:
        stats = log_module.stats()
        last = log_module.last_error()
        parts = ["level %s" % stats["level"], "errors %d" % stats["errors"]]
        if last:
            parts.append(last[:80])
        return " · ".join(parts)

    def _state_key(self) -> str:
        if state.render_state == state.STATE_RUNNING:
            return "perf_state_running"
        if state.render_state == state.STATE_PAUSED:
            return "perf_state_paused"
        return "perf_state_off"


def _media_mime_types() -> Any:
    """MIME whitelist for the file picker, built as a Java string array."""
    values = ["image/*", "video/*"]
    try:
        from java import jarray  # type: ignore
        from java.lang import String  # type: ignore

        array = jarray(String)(len(values))
        for index, value in enumerate(values):
            array[index] = value
        return array
    except Exception:
        return values
