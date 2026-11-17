#!/usr/bin/env python3
"""Load a built .elyx archive with the rules the real Elyx engine uses.

The smoke test runs against the repository. This script runs against the
*archive* — the exact bytes that get installed — and reproduces the importer
behaviour that already broke the plugin twice:

* the entry module comes from ``refmap.yml`` (``main``) and is executed as a
  module whose ``__file__`` points into the plugin directory;
* plugin-local imports resolve against the plugin root, never ``sys.path``;
* packages are created with ``spec_from_loader(..., is_package=True)``, which
  leaves ``__path__`` empty, so ``import core.assets`` cannot work at all;
* the plugin object is constructed as ``PluginClass(plugin_id, plugin_path)``
  and has only the Elyx surface (``id``, ``getId``, ``getPluginPath``, ...),
  with no ``getName``/``version``;
* ``on_plugin_load`` and ``on_plugin_unload`` are invoked.

Java/SDK modules are stubbed: the goal is to catch Python-level integration
errors (imports, attribute names, signatures) before installing on a phone.

    python3 tools/verify_archive.py builds/custom_extra_ayu-1.0.3-20261117.elyx
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import os
import pathlib
import shutil
import sys
import tempfile
import types

RESERVED = {
    "android", "androidx", "base_plugin", "client_utils", "com", "de", "elyx",
    "hook_utils", "importlib", "java", "org", "ui", "sys", "builtins", "os",
    "json", "pathlib", "typing", "types", "re", "locale", "time", "traceback",
    "collections", "hashlib", "math", "random", "threading", "urllib", "yaml",
    "requests", "io", "shutil", "zipfile", "marshal", "glob", "struct",
}


class Any:
    """Accepts any attribute access or call — a Java object stand-in."""

    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return Any()

    def __call__(self, *args, **kwargs):
        return Any()

    def __bool__(self):
        return False


class _AnyTypeMeta(type):
    def __getattr__(cls, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return name


class AnyType(metaclass=_AnyTypeMeta):
    """Stand-in for Java/SDK *classes*: attribute access yields the name itself."""


class Logger:
    def __init__(self, lines=None):
        self.lines = lines if lines is not None else []
        self.level = None

    def add_handler(self, handler):
        self.lines.append("handler added")

    def remove_handler(self, handler):
        return True

    def _log(self, *args, **kwargs):
        if args:
            self.lines.append(str(args[0]))

    verbose = debug = info = warning = error = exception = dump = _log

    def child(self, name):
        return self


def stub_modules(plugin_root, log_lines, plugin_base):
    def module(name, **attrs):
        mod = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(mod, key, value)
        sys.modules[name] = mod
        return mod

    module("base_plugin", BasePlugin=plugin_base, HookResult=Any, HookStrategy=AnyType,
           AppEvent=AnyType, MenuItemData=Any, MenuItemType=AnyType, HookFilter=object,
           MethodHook=object, MethodReplacement=object)
    module("ui")
    module("ui.settings", Header=Any, Divider=Any, Switch=Any, Selector=Any, Input=Any,
           Text=Any, EditText=Any, Custom=Any, SimpleSettingFactory=Any)
    module("ui.bulletin", BulletinHelper=Any)
    module("ui.alert", AlertDialogBuilder=Any)
    module("android_utils", run_on_ui_thread=lambda fn, *a, **k: fn(), log=lambda *a, **k: None,
           copy_to_clipboard=lambda *a, **k: None, R=lambda fn: fn,
           OnClickListener=Any, OnLongClickListener=Any)
    module("client_utils", run_on_queue=lambda fn, *a, **k: fn(),
           get_last_fragment=lambda *a, **k: None, get_messages_controller=lambda *a, **k: None,
           get_user_config=lambda *a, **k: None, get_notification_center=lambda *a, **k: None,
           send_text=lambda *a, **k: None)
    module("hook_utils", find_class=lambda *a, **k: None, get_private_field=lambda *a, **k: None,
           set_private_field=lambda *a, **k: None,
           get_static_private_field=lambda *a, **k: None,
           set_static_private_field=lambda *a, **k: None)
    module("file_utils", get_plugins_dir=lambda: os.path.dirname(plugin_root),
           ensure_dir_exists=lambda path: os.makedirs(path, exist_ok=True) or True,
           read_file=lambda path: pathlib.Path(path).read_text(encoding="utf-8")
           if os.path.exists(path) else None,
           write_file=lambda path, content: bool(pathlib.Path(path).write_text(content, encoding="utf-8")))
    module("log_utils", LogLevel=types.SimpleNamespace(VERBOSE=2, DEBUG=3, INFO=4, WARNING=5,
                                                       ERROR=6, OFF=7),
           get_logger=lambda *a, **k: Logger(log_lines), dump=lambda *a, **k: "")
    module("_sdk_version", __version__="1.4.6.3", __start__=lambda: True, __beta__=False)


class SDKImporter(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Elyx importer, faithful to elyxcore/_importer.py."""

    def __init__(self, root):
        self.root = pathlib.Path(root).resolve()

    def _root_for(self, filename):
        return self.root if str(self.root) in str(filename) else None

    def caller_root(self):
        frame = sys._getframe(1)
        while frame is not None:
            if self._root_for(frame.f_code.co_filename):
                return self.root
            frame = frame.f_back
        return None

    def _resolve(self, fullname):
        relative = pathlib.Path(*fullname.split("."))
        for candidate in (self.root / relative.with_suffix(".py"),
                          self.root / relative / "__init__.py"):
            if candidate.is_file():
                return candidate
        candidate = self.root / relative
        return candidate if candidate.is_dir() else None

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in RESERVED:
            return None
        if self.caller_root() is None:
            return None
        resolved = self._resolve(fullname)
        if resolved is None:
            return None
        is_pkg = resolved.is_dir() or resolved.name == "__init__.py"
        # note: no submodule_search_locations -> package __path__ stays empty
        return importlib.util.spec_from_loader(fullname, self, origin=str(resolved),
                                               is_package=is_pkg)

    def create_module(self, spec):
        module = types.ModuleType(spec.name)
        module.__spec__ = spec
        module.__loader__ = self
        module.__file__ = spec.origin or ""
        module.__package__ = spec.name.rpartition(".")[0]
        return module

    def exec_module(self, module):
        path = pathlib.Path(module.__file__)
        if path.is_dir():
            return
        code = compile(path.read_text(encoding="utf-8"), str(path), "exec")
        exec(code, module.__dict__)


class HostPlugin:
    """What ``elyxcore._plugin.ElyxPlugin`` gives the plugin at runtime."""

    # Names BasePlugin.__init__ assigns. A subclass property with one of these
    # names raises "property has no setter" inside the base constructor, which
    # is invisible to any harness that does not assign them too.
    OWNED_ATTRIBUTES = ("id", "name", "description", "author", "version",
                        "min_version", "icon", "error_message", "enabled",
                        "initialized", "isenabled")

    def __init__(self, plugin_id="", plugin_path=""):
        self.id = plugin_id
        self.name = ""
        self.description = ""
        self.author = ""
        self.version = ""
        self.min_version = ""
        self.icon = None
        self.error_message = None
        self.enabled = False
        self.initialized = False
        self.isenabled = False
        self._plugin_id = plugin_id
        self._plugin_path = plugin_path
        self.logger = Logger()
        self._settings = {}
        self.height = 0
        self.plugin_strings = {}

    def init(self, engine=None, plugin_path=None):
        """What the engine calls right after constructing the instance."""
        if plugin_path:
            self._plugin_path = plugin_path
        self.id = self._plugin_id

    def getId(self):
        return self._plugin_id

    def getPluginPath(self):
        return self._plugin_path

    def get_metainfo(self):
        import yaml

        for name in ("metainfo.yml", "metainfo.yaml"):
            candidate = os.path.join(self._plugin_path, name)
            if os.path.isfile(candidate):
                with open(candidate, "r", encoding="utf-8") as handle:
                    return yaml.safe_load(handle) or {}
        return {}

    def get_setting(self, key, default=None):
        return self._settings.get(key, default)

    def set_setting(self, key, value, reload_settings=False):
        self._settings[key] = value

    def add_menu_item(self, data):
        return "menu-%d" % id(data)

    def remove_menu_item(self, item_id):
        return True

    def add_hook(self, *args, **kwargs):
        return None

    add_on_send_message_hook = add_hook
    add_file_hook = add_hook
    add_intent_hook = add_hook
    remove_hook = add_hook
    remove_file_hook = add_hook
    remove_intent_hook = add_hook

    def hook_method(self, *args, **kwargs):
        return object()

    hook_all_methods = hook_method
    hook_all_constructors = hook_method

    def create_settings(self):
        return []


def read_refmap(root):
    path = os.path.join(root, "refmap.yml")
    entry = "main.py"
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip().startswith("main:"):
                    entry = line.split(":", 1)[1].strip().strip('"').strip("'") or entry
    return entry


def find_plugin_class(module):
    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, type) and issubclass(obj, HostPlugin) and obj is not HostPlugin:
            return obj
        if isinstance(obj, type) and getattr(obj, "__module__", None) == module.__name__:
            if name.lower().endswith("plugin"):
                return obj
    return None


def verify(archive_path):
    workdir = tempfile.mkdtemp(prefix="ayu-verify-")
    plugins = os.path.join(workdir, "plugins")
    os.makedirs(plugins, exist_ok=True)
    root = os.path.join(plugins, "custom_extra_ayu")
    with __import__("zipfile").ZipFile(archive_path) as archive:
        archive.extractall(root)

    log_lines = []
    stub_modules(root, log_lines, HostPlugin)
    importer = SDKImporter(root)
    sys.meta_path.append(importer)
    # the runtime is a real host: yaml is available there, keep it available here
    entry = read_refmap(root)
    module_name = os.path.splitext(entry)[0]

    spec = importlib.util.spec_from_loader(module_name, importer,
                                           origin=os.path.join(root, entry), is_package=False)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    importer.exec_module(module)

    plugin_class = find_plugin_class(module)
    if plugin_class is None:
        raise SystemExit("no plugin class found in the archive")

    plugin = plugin_class("custom_extra_ayu", root)
    # ElyxPlugin.init() runs before the host calls the lifecycle
    plugin.init(None, root)
    plugin.on_plugin_load()
    rows = plugin.create_settings()
    plugin.on_plugin_unload()

    shutil.rmtree(workdir, ignore_errors=True)
    print("verified: %s" % os.path.basename(archive_path))
    print("  entry: %s" % entry)
    print("  plugin class: %s" % plugin_class.__name__)
    print("  settings rows: %d" % len(rows))
    print("  log lines: %d" % len(log_lines))
    for line in log_lines[:8]:
        print("    | %s" % line)
    return 0


def main():
    if len(sys.argv) < 2:
        print("usage: verify_archive.py <archive.elyx>", file=sys.stderr)
        return 2
    try:
        return verify(sys.argv[1])
    except Exception:
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
