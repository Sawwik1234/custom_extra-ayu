"""Logging layer for Custom Extra Ayu.

Why this exists on top of ``self.logger``:

* the SDK logger writes to logcat, which is not available from the plugin UI, so
  the plugin keeps a small ring buffer to make "Copy log" show the real lines;
* hot paths (hook callbacks, frame errors, decode failures) must not spam, so
  repeated messages are collapsed through :meth:`Logger.once`;
* every module gets a child tag, which makes ``adb logcat -s plugin.custom_extra_ayu``
  readable without guessing where a line came from.

Usage:

    from core import log
    log.bind(plugin.logger)          # once, during on_plugin_load
    log.get(__name__).info("...")    # everywhere else

Logging never raises: if the SDK logger is missing or broken, messages go to the
ring buffer and, when possible, to ``android_utils.log``.
"""

from __future__ import annotations

import time
import traceback
from collections import deque
from typing import Any, Deque, Dict, Optional, Tuple

# Levels ordered like logcat priorities.
VERBOSE = 2
DEBUG = 3
INFO = 4
WARNING = 5
ERROR = 6
OFF = 7

LEVEL_NAMES = {
    VERBOSE: "V",
    DEBUG: "D",
    INFO: "I",
    WARNING: "W",
    ERROR: "E",
    OFF: "O",
}

BUFFER_SIZE = 400

_host: Any = None
_level: int = INFO
_writing = False
_ring: Deque[Tuple[float, int, str, str]] = deque(maxlen=BUFFER_SIZE)
_once_keys: Dict[str, float] = {}
_errors: Deque[str] = deque(maxlen=20)


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
def bind(host_logger: Any) -> None:
    """Attach the SDK logger and register a capture handler on it."""
    global _host
    _host = host_logger
    if host_logger is None:
        return
    handler = getattr(host_logger, "add_handler", None)
    if handler is None:
        return
    try:
        handler(_capture_record)
    except Exception:
        pass


def set_level(level: Any) -> None:
    """Accept an int, a name ("debug") or an SDK ``LogLevel`` value."""
    global _level
    value = level
    if isinstance(level, str):
        mapping = {
            "verbose": VERBOSE,
            "debug": DEBUG,
            "info": INFO,
            "warning": WARNING,
            "error": ERROR,
            "off": OFF,
        }
        value = mapping.get(level.lower(), INFO)
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = INFO
    _level = max(VERBOSE, min(OFF, number))
    _apply_host_level(_level)


def level() -> int:
    return _level


def _apply_host_level(number: int) -> None:
    if _host is None:
        return
    try:
        from log_utils import LogLevel  # type: ignore

        mapping = {
            VERBOSE: LogLevel.VERBOSE,
            DEBUG: LogLevel.DEBUG,
            INFO: LogLevel.INFO,
            WARNING: LogLevel.WARNING,
            ERROR: LogLevel.ERROR,
            OFF: LogLevel.OFF,
        }
        _host.level = mapping.get(number)
    except Exception:
        pass


def _capture_record(record: Any) -> None:
    """SDK handler: mirror the host's own records into the ring buffer."""
    try:
        level_value = int(getattr(record, "level", INFO))
    except Exception:
        level_value = INFO
    if level_value < VERBOSE:
        level_value = VERBOSE
    tag = str(getattr(record, "tag", "plugin"))
    message = str(getattr(record, "message", ""))
    _push(level_value, tag, message)


# ---------------------------------------------------------------------------
# Ring buffer
# ---------------------------------------------------------------------------
def _push(level_value: int, tag: str, message: str) -> None:
    _ring.append((time.time(), level_value, tag, message))
    if level_value >= ERROR:
        _errors.append(message)


def _emit(level_value: int, tag: str, message: str) -> None:
    if level_value < _level:
        return
    _push(level_value, tag, message)
    if _host is None:
        _fallback(level_value, message)
        return
    global _writing
    if _writing:  # a handler logging from a handler would recurse
        return
    _writing = True
    try:
        method = {
            VERBOSE: getattr(_host, "verbose", None),
            DEBUG: _host.debug,
            INFO: _host.info,
            WARNING: _host.warning,
            ERROR: _host.error,
        }.get(level_value, _host.info)
        method("[%s] %s", tag, message)
    except Exception:
        _fallback(level_value, message)
    finally:
        _writing = False


def _fallback(level_value: int, message: str) -> None:
    try:
        from android_utils import log as android_log  # type: ignore

        android_log("[%s] %s" % (LEVEL_NAMES.get(level_value, "I"), message))
    except Exception:
        pass


def recent(limit: int = 120, minimum: int = VERBOSE) -> str:
    """Format the tail of the buffer for the clipboard."""
    lines = []
    for stamp, level_value, tag, message in list(_ring)[-limit:]:
        if level_value < minimum:
            continue
        clock = time.strftime("%H:%M:%S", time.localtime(stamp))
        lines.append("%s %s/%s: %s" % (clock, LEVEL_NAMES.get(level_value, "I"), tag, message))
    return "\n".join(lines)


def count() -> int:
    return len(_ring)


def error_count() -> int:
    return len(_errors)


def last_error() -> Optional[str]:
    return _errors[-1] if _errors else None


def clear() -> None:
    _ring.clear()
    _errors.clear()
    _once_keys.clear()


def stats() -> Dict[str, Any]:
    return {
        "buffered": len(_ring),
        "errors": len(_errors),
        "level": LEVEL_NAMES.get(_level, "I"),
    }


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
class Logger:
    """Small wrapper with a tag, a level check and de-duplication."""

    __slots__ = ("tag",)

    def __init__(self, tag: str) -> None:
        self.tag = tag

    # -- level checks ---------------------------------------------------
    def is_enabled_for(self, level_value: int) -> bool:
        return level_value >= _level

    # -- emit -----------------------------------------------------------
    def _log(self, level_value: int, message: str, *args: Any) -> None:
        if level_value < _level:
            return
        text = _format(message, args)
        _emit(level_value, self.tag, text)

    def verbose(self, message: str, *args: Any) -> None:
        self._log(VERBOSE, message, *args)

    def debug(self, message: str, *args: Any) -> None:
        self._log(DEBUG, message, *args)

    def info(self, message: str, *args: Any) -> None:
        self._log(INFO, message, *args)

    def warning(self, message: str, *args: Any) -> None:
        self._log(WARNING, message, *args)

    def error(self, message: str, *args: Any) -> None:
        self._log(ERROR, message, *args)

    def exception(self, message: str, *args: Any) -> None:
        text = _format(message, args)
        detail = traceback.format_exc(limit=4).strip().replace("\n", " | ")
        self._log(ERROR, "%s :: %s" % (text, detail))

    # -- helpers --------------------------------------------------------
    def once(self, key: str, message: str, *args: Any, level_value: int = DEBUG,
             cooldown: float = 60.0) -> None:
        """Log at most once per ``cooldown`` seconds for a given key."""
        now = time.time()
        last = _once_keys.get(key)
        if last is not None and (now - last) < cooldown:
            return
        _once_keys[key] = now
        self._log(level_value, message, *args)

    def timed(self, label: str, level_value: int = DEBUG) -> "Timer":
        return Timer(self, label, level_value)

    def child(self, name: str) -> "Logger":
        return Logger("%s.%s" % (self.tag, name))

    def dump(self, obj: Any, label: Optional[str] = None) -> None:
        if DEBUG < _level:
            return
        try:
            from log_utils import dump as sdk_dump  # type: ignore

            text = sdk_dump(obj, depth=2)
        except Exception:
            try:
                text = repr(obj)
            except Exception:
                text = "<unprintable>"
        self._log(DEBUG, "%s%s" % ((label + ": ") if label else "", text))


class Timer:
    """Context manager that logs how long a block took."""

    __slots__ = ("logger", "label", "level_value", "started", "ok")

    def __init__(self, logger: Logger, label: str, level_value: int) -> None:
        self.logger = logger
        self.label = label
        self.level_value = level_value
        self.started = 0.0
        self.ok = True

    def __enter__(self) -> "Timer":
        self.started = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        elapsed = (time.perf_counter() - self.started) * 1000.0
        if exc_type is not None:
            self.ok = False
            self.logger._log(
                ERROR,
                "%s failed after %.1f ms :: %s: %s" % (self.label, elapsed, exc_type.__name__, exc),
            )
        else:
            self.logger._log(self.level_value, "%s took %.1f ms" % (self.label, elapsed))
        return False


# ---------------------------------------------------------------------------
# Module-level access
# ---------------------------------------------------------------------------
_short_tags: Dict[str, str] = {
    "main": "plugin",
    "core.files": "files",
    "core.engine": "engine",
    "core.net": "net",
    "core.images": "images",
    "core.theme": "theme",
    "core.javabridge": "reflect",
    "core.l10n": "l10n",
    "core.prefs": "prefs",
    "core.assets": "assets",
    "core.compat": "compat",
    "wallpaper.service": "wallpaper",
    "wallpaper.attach": "attach",
    "wallpaper.host": "host",
    "wallpaper.overrides": "overrides",
    "wallpaper.renderers": "render",
    "wallpaper.renderers.gradient": "render.gradient",
    "wallpaper.renderers.parallax": "render.parallax",
    "wallpaper.renderers.particles": "render.particles",
    "wallpaper.renderers.video": "render.video",
    "themes.model": "themes",
    "skins.registry": "skins",
    "skins.apply": "skins.apply",
    "ayu_ui.pages": "ui.pages",
    "ayu_ui.dialogs": "ui.dialogs",
    "i18n": "i18n",
}


def get(name: str) -> Logger:
    """Return a logger for a module name, shortened for the log tag."""
    tag = _short_tags.get(name)
    if tag is None:
        tag = name.rsplit(".", 1)[-1]
    return Logger(tag)


def _format(message: str, args: Tuple[Any, ...]) -> str:
    if not args:
        return str(message)
    try:
        return str(message) % args
    except Exception:
        return "%s %s" % (message, args)
