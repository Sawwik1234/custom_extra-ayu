#!/usr/bin/env python3
"""Desktop smoke test with a fake client host.

The plugin cannot run on a PC, but the pure-Python half can: settings rows,
color maths, overrides, themes, cache helpers and the settings page builders all
run against stubs. This catches typos and bad signatures before installing on a
phone.

    python3 tools/smoke_test.py
"""

from __future__ import annotations

import importlib
import importlib.machinery
import importlib.util
import os
import pathlib
import sys
import types

# AYU_ROOT lets the same test run against an extracted archive:
#   unzip -q builds/*.elyx -d /tmp/ayu && AYU_ROOT=/tmp/ayu python3 tools/smoke_test.py
ROOT = os.environ.get("AYU_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.abspath(ROOT)
SRC = os.path.join(ROOT, "src")
# NOTE: plugin-local modules are resolved by the SDK importer as
# ``elyx_plugins.<plugin_id>.*``; local modules are intentionally NOT on sys.path, so
# the smoke test reproduces the device import rules.


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
        self.handlers = []

    def add_handler(self, handler):
        self.handlers.append(handler)

    def remove_handler(self, handler):
        try:
            self.handlers.remove(handler)
            return True
        except ValueError:
            return False

    def _log(self, level, message, *args):
        try:
            text = message % args if args else str(message)
        except Exception:
            text = str(message)
        self.lines.append("%s %s" % (level, text))

    def verbose(self, message, *args, **kwargs):
        self._log("V", message, *args)

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
    """Mirrors ``elyxcore._plugin.ElyxPlugin``, not the legacy BasePlugin.

    Deliberate omissions, because the real class does not have them:

    * ``getName()`` — never existed on Elyx plugins;
    * ``version`` / ``sdk_version`` — were single-file plugin module constants
      that the old host patched onto the instance; an Elyx plugin reads them
      from ``metainfo.yml`` instead.

    A stub that invents these attributes hides exactly the AttributeError the
    device throws, which is how "loaded %s v%s" reached a phone broken.
    """

    def __init__(self, plugin_id="custom_extra_ayu", plugin_path=None):
        self.id = plugin_id
        self._plugin_path = plugin_path or ROOT
        self.logger = FakeLogger()
        self._settings = {}
        self._hooks = []

    # ElyxPlugin surface used by the plugin
    def getId(self):
        return self.id

    def getPluginPath(self):
        return self._plugin_path

    def get_metainfo(self):
        return {}

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


class FakeSDKImporter:
    """Mimics the Elyx importer closely enough to catch layout mistakes.

    Facts taken from the SDK source (``elyxcore/_importer.py``):

    * plugin-local modules resolve against the plugin *root*, not from
      ``sys.path`` and not from the folder of the entry file;
    * the entry module is ``<root>/main.py``;
    * packages are built with
      ``spec_from_loader(..., is_package=True)``, and that call leaves
      ``submodule_search_locations`` empty — ``import core`` works, while
      ``import core.assets`` fails with "unknown location".

    The last point is why this stub refuses subpackages outright: on device a
    directory-based layout can never be imported, so the test would be lying if
    it allowed one.
    """

    ENTRY = "main"

    def __init__(self):
        self.root = ROOT

    def find_spec(self, fullname, path=None, target=None):
        base = os.path.join(self.root, *fullname.split("."))
        if os.path.isfile(base + ".py"):
            loader = importlib.machinery.SourceFileLoader(fullname, base + ".py")
            return importlib.util.spec_from_file_location(fullname, base + ".py", loader=loader)
        if os.path.isdir(base):
            # Elyx hands out a package nobody can put submodules into.
            spec = importlib.machinery.ModuleSpec(fullname, self, is_package=True)
            spec.submodule_search_locations = []
            return spec
        return None

    def create_module(self, spec):
        module = types.ModuleType(spec.name)
        module.__file__ = spec.origin or os.path.join(self.root, spec.name)
        return module

    def exec_module(self, module):
        if module.__spec__.origin is None or os.path.isdir(module.__file__):
            return  # empty package, exactly what the device gets
        with open(module.__file__, "r", encoding="utf-8") as handle:
            code = compile(handle.read(), module.__file__, "exec")
        exec(code, module.__dict__)

    def install(self):
        # Elyx finder sits in front of the standard one and only handles
        # plugin-local names; here the plugin root is a real directory, so the
        # finder has to stay last to keep stdlib and SDK imports working.
        sys.meta_path.append(self)


def load_plugin_module():
    """Import the entry module the way the SDK does: ``<root>/main.py``."""
    import importlib

    if FakeSDKImporter.ENTRY in sys.modules:
        return sys.modules[FakeSDKImporter.ENTRY]
    return importlib.import_module(FakeSDKImporter.ENTRY)


def plugin_import(name):
    """Import a plugin-local module the way plugin code does."""
    return importlib.import_module(name)


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
    FakeSDKImporter().install()

    i18n = plugin_import("ayu_i18n")
    i18n.init()

    colors = plugin_import("ayu_colors")
    files = plugin_import("ayu_files")
    prefs = plugin_import("ayu_prefs")
    state = plugin_import("ayu_state")
    Overrides = plugin_import("ayu_overrides").Overrides
    themes_model = plugin_import("ayu_themes")

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
        plugin_main = load_plugin_module()

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
        plugin_main = load_plugin_module()

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

    def t_logging():
        log_module = plugin_import("ayu_log")

        class HostLogger(FakeLogger):
            pass

        host = HostLogger()
        log_module.clear()
        log_module.bind(host)
        log_module.set_level("debug")
        logger = log_module.get("wallpaper.attach")
        logger.info("hello %s", "world")
        logger.debug("detail %d", 7)
        logger.warning("careful")
        logger.error("broken")
        logger.exception("with traceback")
        logger.once("k", "repeat")
        logger.once("k", "repeat")
        with logger.timed("work"):
            pass
        logger.child("sub").info("child line")
        logger.dump({"a": 1}, "payload")

        text = log_module.recent()
        assert "hello world" in text, text
        assert "attach" in text
        assert text.count("repeat") == 1, "once() should de-duplicate"
        assert "took" in text, "timer output missing"
        assert log_module.error_count() >= 2
        assert log_module.last_error()
        stats = log_module.stats()
        assert stats["buffered"] > 5

        # host logger receives the same lines
        joined = "\n".join(host.lines)
        assert "hello world" in joined, joined

        # level filtering
        log_module.set_level("error")
        before = len(log_module.recent(limit=500))
        logger.debug("should be dropped")
        assert "should be dropped" not in log_module.recent(limit=500)
        log_module.set_level("debug")

        # broken host logger must not raise
        class Broken:
            level = None

            def __getattr__(self, name):
                def boom(*args, **kwargs):
                    raise RuntimeError("host logger is broken")

                return boom

            def add_handler(self, handler):
                raise RuntimeError("cannot add")

        log_module.bind(Broken())
        broke = log_module.get("core.files")
        broke.warning("still works")
        assert "still works" in log_module.recent(limit=50)

    check("logging layer", t_logging)

    def t_package_layout():
        """The archive must be importable by the Elyx importer.

        Two rules, both learned the hard way on a device:

        1. every plugin-local import must exist at the archive root — a nested
           ``src/`` folder is not on the import path Elyx uses;
        2. no subdirectories at all. Elyx builds packages with an empty
           ``__path__``, so ``import core`` works and ``import core.assets``
           fails with "unknown location". Flat modules are the only layout that
           survives, which is why the code is a set of ``ayu_*.py`` files.
        """

        import ast

        root = pathlib.Path(ROOT)
        entry = "main.py"
        local = {path.stem for path in root.glob("*.py")}

        folders = [path.name for path in root.iterdir() if path.is_dir() and not path.name.startswith(".")]
        allowed_folders = {"locales", "res", "tools", "docs", "builds", "__pycache__"}
        stray = sorted(set(folders) - allowed_folders)
        assert not stray, (
            "directories are not importable in a plugin: %s — move their modules to the "
            "archive root as flat files" % stray
        )

        missing = []
        for path in sorted(root.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    names = [node.module]
                elif isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                for name in names:
                    if name.split(".")[0] not in local:
                        continue
                    if not os.path.isfile(os.path.join(ROOT, *name.split(".")) + ".py"):
                        missing.append("%s -> %s" % (path.name, name))
        assert not missing, "imports Elyx cannot resolve: %s" % missing

        refmap = pathlib.Path(ROOT, "refmap.yml").read_text(encoding="utf-8")
        declared = [line.split(":", 1)[1].strip() for line in refmap.splitlines() if line.startswith("main:")][0]
        assert os.path.isfile(os.path.join(ROOT, declared)), "refmap main points to a missing file: %s" % declared
        assert os.path.isfile(os.path.join(ROOT, entry)), "entry module must be %s" % entry

    check("package layout (Elyx import roots)", t_package_layout)

    def t_legacy_attributes():
        """The plugin must never touch single-file-plugin-only attributes.

        ``getName()``, ``version`` and ``sdk_version`` do not exist on
        ``ElyxPlugin``. Reading them raised
        ``AttributeError: 'CustomExtraAyuPlugin' object has no attribute 'getName'``
        inside ``on_plugin_load`` and left the plugin unusable, so the names are
        checked statically as well as through the lifecycle above.
        """

        import ast

        forbidden = {"getName", "sdkVersion"}
        offenders = []
        for path in sorted(pathlib.Path(ROOT).glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and node.attr in forbidden:
                    offenders.append("%s: self.%s" % (path.name, node.attr))
                if (isinstance(node, ast.Attribute) and node.attr in {"version", "sdk_version", "name"}
                        and isinstance(node.value, ast.Name) and node.value.id == "self"
                        and isinstance(node.ctx, ast.Store)):
                    offenders.append("%s: writes self.%s" % (path.name, node.attr))
        assert not offenders, "legacy BasePlugin attributes used by an Elyx plugin: %s" % offenders

        plugin_main = load_plugin_module()
        meta = plugin_import("ayu_meta")
        assert meta.version() == plugin_main.CustomExtraAyuPlugin().version, "version must come from metainfo"
        assert meta.name(), "metainfo name is empty"

    check("no legacy plugin attributes", t_legacy_attributes)

    print()
    if FAILURES:
        print("FAILED: %s" % ", ".join(FAILURES))
        return 1
    print("all smoke tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
