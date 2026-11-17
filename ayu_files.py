"""Plugin storage: folders, the media cache and small JSON state files.

Every path lives under ``plugins/custom_extra_ayu`` so that removing the plugin
removes its data with it.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, Dict, Optional, Tuple

from ayu_log import get as _get_logger

PLUGIN_ID = "custom_extra_ayu"

MEDIA_DIRS = ("cache", "backgrounds", "skins", "themes", "tmp")
CACHE_TTL_SECONDS = 7 * 24 * 3600
CACHE_MAX_BYTES = 32 * 1024 * 1024

_available = True
_plugins_dir = ""

try:  # pragma: no cover - host modules
    from file_utils import (  # type: ignore
        ensure_dir_exists,
        get_plugins_dir,
        read_file,
        write_file,
    )
except Exception:  # pragma: no cover
    _available = False

    def get_plugins_dir() -> str:  # type: ignore
        return "/data/user/0/com.exteragram.messenger/files/plugins"

    def ensure_dir_exists(path: str) -> bool:  # type: ignore
        try:
            os.makedirs(path, exist_ok=True)
            return True
        except Exception:
            return False

    def read_file(path: str) -> Optional[str]:  # type: ignore
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return handle.read()
        except Exception:
            return None

    def write_file(path: str, content: str) -> bool:  # type: ignore
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(content)
            return True
        except Exception:
            return False


_log = _get_logger("core.files")


def _warn(message: str) -> None:
    _log.warning(message)


def init() -> None:
    """Create the plugin folder tree once during load."""
    global _plugins_dir
    try:
        _plugins_dir = os.path.join(str(get_plugins_dir()), PLUGIN_ID)
    except Exception as error:
        _warn("plugins dir unavailable: %s" % error)
        _plugins_dir = ""
        return
    for name in MEDIA_DIRS:
        ensure_dir_exists(os.path.join(_plugins_dir, name))
    _log.debug("storage ready at %s", _plugins_dir)


def root() -> str:
    return _plugins_dir


def path(*parts: str) -> str:
    if not _plugins_dir:
        init()
    return os.path.join(_plugins_dir, *parts)


def cache_dir() -> str:
    return path("cache")


def skins_dir() -> str:
    return path("skins")


def themes_dir() -> str:
    return path("themes")


def ensure(path_value: str) -> bool:
    return bool(ensure_dir_exists(path_value))


def exists(path_value: str) -> bool:
    try:
        return os.path.exists(path_value)
    except Exception:
        return False


def file_size(path_value: str) -> int:
    try:
        return os.path.getsize(path_value)
    except Exception:
        return 0


def extension(path_value: str) -> str:
    try:
        return os.path.splitext(path_value)[1].lower().lstrip(".")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Small JSON state files
# ---------------------------------------------------------------------------
def read_json(name: str, default: Any = None) -> Any:
    target = path(name)
    if not exists(target):
        return {} if default is None else default
    raw = read_file(target)
    if not raw:
        return {} if default is None else default
    try:
        return json.loads(raw)
    except Exception as error:
        _warn("cannot parse %s: %s" % (name, error))
        return {} if default is None else default


def write_json(name: str, data: Any) -> bool:
    try:
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    except Exception as error:
        _warn("cannot serialize %s: %s" % (name, error))
        return False
    return bool(write_file(path(name), payload))


# ---------------------------------------------------------------------------
# Media cache
# ---------------------------------------------------------------------------
def url_cache_path(url: str) -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    return path("cache", "url_%s" % digest)


def copy_to_cache(source_path: str, prefix: str = "file") -> Optional[str]:
    """Copy a picked file into the cache so the app keeps access to it."""
    try:
        stamp = str(int(time.time()))
        digest = hashlib.sha256(source_path.encode("utf-8")).hexdigest()[:12]
        ext = extension(source_path) or "bin"
        target = path("cache", "%s_%s_%s.%s" % (prefix, digest, stamp, ext))
        ensure(path("cache"))
        _log.debug("copying %s -> %s", os.path.basename(source_path), os.path.basename(target))
        with open(source_path, "rb") as src, open(target, "wb") as dst:
            while True:
                chunk = src.read(256 * 1024)
                if not chunk:
                    break
                dst.write(chunk)
        return target
    except Exception as error:
        _warn("cannot copy %s: %s" % (source_path, error))
        return None


def write_bytes(target: str, data: bytes) -> bool:
    try:
        ensure(os.path.dirname(target))
        with open(target, "wb") as handle:
            handle.write(data)
        return True
    except Exception as error:
        _warn("cannot write %s: %s" % (target, error))
        return False


def copy_from_uri(uri: Any, prefix: str = "picked", max_bytes: int = 64 * 1024 * 1024) -> Optional[str]:
    """Copy a content:// URI (file-manager pick) into the plugin cache."""
    try:
        import ayu_javabridge as javabridge

        context = javabridge.application_context()
        if context is None:
            return None
        resolver = context.getContentResolver()
        stream = resolver.openInputStream(uri)
        if stream is None:
            return None
        extension = "bin"
        try:
            name = str(resolver.getType(uri) or "")
            if "/" in name:
                extension = name.split("/")[-1]
            if extension in ("jpeg",):
                extension = "jpg"
            if extension in ("mpeg", "quicktime"):
                extension = "mp4"
        except Exception:
            pass

        stamp = str(int(time.time()))
        digest = hashlib.sha256(str(uri).encode("utf-8")).hexdigest()[:12]
        target = path("cache", "%s_%s_%s.%s" % (prefix, digest, stamp, extension))
        ensure(path("cache"))
        written = 0
        with open(target, "wb") as handle:
            buffer = bytearray(128 * 1024)
            array = _byte_array(128 * 1024)
            while True:
                read = stream.read(array)
                if read is None or read <= 0:
                    break
                written += read
                if written > max_bytes:
                    handle.close()
                    _remove_file(target)
                    return None
                handle.write(bytes(array[:read]))
        try:
            stream.close()
        except Exception:
            pass
        return target if written else None
    except Exception as error:
        _warn("cannot copy uri: %s" % error)
        return None


def _byte_array(size: int) -> Any:
    try:
        from java import jarray, jbyte  # type: ignore

        return jarray(jbyte)(size)
    except Exception:
        return bytearray(size)


def _remove_file(path_value: str) -> None:
    try:
        if path_value and os.path.exists(path_value):
            os.remove(path_value)
    except Exception:
        pass


def prune_cache(now: Optional[float] = None) -> Tuple[int, int]:
    """Drop stale and oversized cache entries. Returns (files, bytes) removed."""
    folder = cache_dir()
    if not exists(folder):
        return (0, 0)
    current = time.time() if now is None else now
    entries = []
    try:
        for name in os.listdir(folder):
            full = os.path.join(folder, name)
            if not os.path.isfile(full):
                continue
            try:
                stat = os.stat(full)
            except Exception:
                continue
            entries.append((stat.st_mtime, stat.st_size, full))
    except Exception:
        return (0, 0)

    removed_files = 0
    removed_bytes = 0

    def drop(item: tuple) -> None:
        nonlocal removed_files, removed_bytes
        try:
            os.remove(item[2])
            removed_files += 1
            removed_bytes += item[1]
        except Exception:
            pass

    fresh = []
    for item in entries:
        if current - item[0] > CACHE_TTL_SECONDS:
            drop(item)
        else:
            fresh.append(item)

    total = sum(item[1] for item in fresh)
    if total > CACHE_MAX_BYTES:
        for item in sorted(fresh, key=lambda entry: entry[0]):
            if total <= CACHE_MAX_BYTES:
                break
            drop(item)
            total -= item[1]

    if removed_files:
        _log.info("cache pruned: %d file(s), %.1f MB", removed_files, removed_bytes / (1024.0 * 1024.0))
    return (removed_files, removed_bytes)


def list_files(folder: str, extensions: Optional[Tuple[str, ...]] = None) -> Dict[str, str]:
    """Map lowercase file stem to absolute path for a flat folder."""
    result: Dict[str, str] = {}
    if not exists(folder):
        return result
    try:
        for name in sorted(os.listdir(folder)):
            full = os.path.join(folder, name)
            if not os.path.isfile(full):
                continue
            ext = extension(full)
            if extensions and ext not in extensions:
                continue
            result[os.path.splitext(name)[0].lower()] = full
    except Exception:
        pass
    return result
