#!/usr/bin/env python3
"""Desktop smoke test with a fake client host.

The plugin cannot run on a PC, but the pure-Python half can: settings rows,
color maths, overrides, themes, cache helpers and the settings page builders all
run against stubs. This catches typos and bad signatures before installing on a
phone.

    python3 tools/smoke_test.py
"""

from __future__ import annotations

import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)


# ---------------------------------------------------------------------------
# Fake host modules
# ---------------------------------------------------------------------------
def _module(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


class FakeLogger:
    def __init__(self):
        self.lines = []
        self.level = None

    def _log(self, level, message, *args):
        try:
            text = message % args if args else str(message)
        except Exception:
            text = str(message)
        self.lines.append("%s %s" % (level, text))

    def debug(self, message, *args, **kwargs):
        self._log("D", message, *args)

    def info(self, message, *args, **kwargs):
        self._log("I", message, *args)

    def warning(self, message, *args, **kwargs):
        self._log("W", message, *args)

    def error(self, message, *args, **kwargs):
        self._log("E", message, *args)

    def exception(self, message, *args, **kwargs):
        self._log("E", message, *args)

    def dump(self, obj, *args, **kwargs):
        self._log("D", repr(obj))

    def child(self, name):
        return self


class FakeHookResult:
    def __init__(self, strategy=None, params=None, request=None, response=None, update=None, updates=None):
        self.strategy = strategy
        self.params = params


class FakeHookStrategy:
    DEFAULT = "default"
    CANCEL = "cancel"
    MODIFY = "modify"
    MODIFY_FINAL = "modify_final"


class FakeAppEvent:
    START = "start"
    STOP = "stop"
    PAUSE = "pause"
    RESUME = "resume"


class FakeMenuItemType:
    MESSAGE_CONTEXT_MENU = "message"
    DRAWER_MENU = "drawer"
    MAIN_MENU = "main"
    CHAT_ACTION_MENU = "chat"
    PROFILE_ACTION_MENU = "profile"


class FakeMenuItemData:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeBasePlugin:
    """Mirrors the parts of BasePlugin the plugin uses."""

    def __init__(self):
        self.logger = FakeLogger()
        self.getName = lambda: "Custom Extra Ayu"
        self.version = "1.0.0"
        self.sdk_version = "1.4.6.3"
        self._settings = {}
        self._hooks = []

    def get_setting(self, key, default=None):
        return self._settings.get(key, default)

    def set_setting(self, key, value, reload_settings=False):
        self._settings[key] = value

    def add_menu_item(self, data):
        self._hooks.append(data)
        return "menu-%d" % len(self._hooks)

    def add_hook(self, *args, **kwargs):
        return None

    def add_on_send_message_hook(self, *args, **kwargs):
        return None

    def hook_method(self, method, before=None, after=None, **kwargs):
        return object()

    def add_on_menu_item(self, *args, **kwargs):
        return None


def install_stubs():
    _module("base_plugin", BasePlugin=FakeBasePlugin, HookResult=FakeHookResult,
            HookStrategy=FakeHookStrategy, AppEvent=FakeAppEvent,
            MenuItemData=FakeMenuItemData, MenuItemType=FakeMenuItemType,
            HookFilter=object, MethodHook=object, MethodReplacement=object)

    sys.modules.setdefault("ui", types.ModuleType("ui"))
    settings_mod = types.ModuleType("ui.settings")
    for row_name in ("Header", "Divider", "Switch", "Selector", "Input", "Text", "EditText", "Custom"):

        class Row:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        Row.__name__ = row_name
        setattr(settings_mod, row_name, Row)
    sys.modules["ui.settings"] = settings_mod

    bulletin_mod = types.ModuleType("ui.bulletin")

    class BulletinHelper:
        shown = []

        @classmethod
        def show_info(cls, message, *args):
            cls.shown.append(("info", message))

        @classmethod
        def show_error(cls, message, *args):
            cls.shown.append(("error", message))

        @classmethod
        def show_success(cls, message, *args):
            cls.shown.append(("success", message))

    bulletin_mod.BulletinHelper = BulletinHelper
    sys.modules["ui.bulletin"] = bulletin_mod

    alert_mod = types.ModuleType("ui.alert")

    class AlertDialogBuilder:
        def __init__(self, *args, **kwargs):
            self.calls = []

        def __getattr__(self, name):
            def recorder(*args, **kwargs):
                self.calls.append((name, args))
                return self

            return recorder

    alert_mod.AlertDialogBuilder = AlertDialogBuilder
    sys.modules["ui.alert"] = alert_mod

    _module("android_utils", run_on_ui_thread=lambda fn, delay=0: fn(), log=lambda *a: None,
            copy_to_clipboard=lambda text: None, R=lambda fn: fn,
            OnClickListener=lambda fn: fn, OnLongClickListener=lambda fn: fn)

    _module("client_utils", run_on_queue=lambda fn, *a, **k: fn(), get_last_fragment=lambda *a, **k: None,
            get_messages_controller=lambda *a, **k: None, get_user_config=lambda *a, **k: None,
            get_notification_center=lambda: None, send_text=lambda *a, **k: None)

    _module("hook_utils", find_class=lambda name: None,
            get_private_field=lambda obj, name: None,
            set_private_field=lambda obj, name, value: False,
            get_static_private_field=lambda cls, name: None,
            set_static_private_field=lambda cls, name, value: False)

    _module("file_utils", get_plugins_dir=lambda: FAKE_ROOT, ensure_dir_exists=lambda path: os.makedirs(path, exist_ok=True) or True,
            read_file=lambda path: open(path, encoding="utf-8").read() if os.path.exists(path) else None,
            write_file=lambda path, content: open(path, "w", encoding="utf-8").write(content) or True)

    _module("log_utils", LogLevel=types.SimpleNamespace(VERBOSE=2, DEBUG=3, INFO=4, WARNING=5, ERROR=6, OFF=7),
            get_logger=lambda name=None: FakeLogger(), dump=lambda obj, **k: repr(obj))


FAKE_ROOT = os.path.join("/tmp", "ayu-smoke", "plugins")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
FAILURES = []


def check(name, fn):
    try:
        fn()
        print("  ok   %s" % name)
    except Exception as error:
        import traceback

        FAILURES.append(name)
        print("  FAIL %s: %s" % (name, error))
        traceback.print_exc()


def main():
    install_stubs()
    import i18n

    i18n.init()

    from core import colors, files, prefs, state
    from wallpaper.overrides import Overrides
    from themes import model as themes_model

    def t_colors():
        assert colors.parse("#FFF") == 0xFFFFFFFF
        assert colors.parse("7C4DFF") == 0xFF7C4DFF
        assert colors.parse("#80FF0000") == 0x80FF0000
        assert colors.parse("nope") is None
        assert colors.to_hex(0xFF7C4DFF) == "#7C4DFF"
        assert colors.contrast(0xFFFFFFFF, 0xFF000000) > 20
        assert colors.readable_text(0xFFFFFFFF) == 0xFF000000

    def t_files():
        files.init()
        assert files.root().endswith("custom_extra_ayu")
        files.write_json("probe.json", {"a": 1})
        assert files.read_json("probe.json")["a"] == 1
        assert files.path("cache").endswith("cache")

    def t_prefs():
        prefs_obj = prefs.Prefs(FakeBasePlugin())
        assert prefs_obj.int("perf_fps") == 30
        prefs_obj.set("perf_fps", 999)
        assert prefs_obj.int("perf_fps") == 60, prefs_obj.int("perf_fps")
        prefs_obj.set("wallpaper_dim", "abc")
        assert prefs_obj.int("wallpaper_dim") == 35
        prefs_obj.reset_all()
        assert prefs_obj.int("perf_fps") == 30

    def t_overrides():
        overrides = Overrides()
        overrides.load()
        overrides.set(123, {"kind": "particles"})
        assert overrides.count() == 1
        assert overrides.get(123)["kind"] == "particles"
        overrides.clear_all()
        assert overrides.count() == 0

    def t_themes():
        themes = themes_model.load_all()
        item = themes_model.create("Test theme", themes_model.read_current_look())
        themes.append(item)
        assert themes_model.save_all(themes)
        loaded = themes_model.load_all()
        assert loaded[-1]["name"] == "Test theme"
        assert themes_model.readability_warning(item) is not None

    check("colors", t_colors)
    check("files", t_files)
    check("prefs", t_prefs)
    check("overrides", t_overrides)
    check("themes", t_themes)

    # Full plugin load with the fake host.
    def t_plugin():
        import main as plugin_main

        plugin = plugin_main.CustomExtraAyuPlugin()
        plugin.on_plugin_load()
        rows = plugin.create_settings()
        assert rows, "settings page is empty"
        assert len(rows) > 40, "expected a rich settings page, got %d rows" % len(rows)
        plugin.apply_performance()
        plugin.on_wallpaper_changed()
        plugin.status_line()
        plugin.copy_log()
        plugin.reset_everything()
        plugin.apply_skins()
        plugin.create_default_skin()
        plugin.on_plugin_unload()

    check("plugin lifecycle + settings", t_plugin)

    def t_pages():
        import main as plugin_main

        plugin = plugin_main.CustomExtraAyuPlugin()
        plugin.on_plugin_load()
        pages = plugin.pages
        for name in (
            "page_wallpaper",
            "page_particles",
            "page_themes",
            "page_skins",
            "page_per_chat",
            "page_performance",
            "page_diagnostics",
        ):
            rows = getattr(pages, name)()
            assert rows, "%s returned no rows" % name
        plugin.on_plugin_unload()

    check("every settings page", t_pages)

    print()
    if FAILURES:
        print("FAILED: %s" % ", ".join(FAILURES))
        return 1
    print("all smoke tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
