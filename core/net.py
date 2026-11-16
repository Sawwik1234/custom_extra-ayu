"""Download helpers with a hard size limit and cache awareness."""

from __future__ import annotations

import os
from typing import Any, Optional, Tuple

from core import files
from core.log import get as _get_logger

_log = _get_logger("core.net")

MAX_DOWNLOAD_BYTES = 24 * 1024 * 1024
CHUNK = 128 * 1024
USER_AGENT = "Mozilla/5.0 (Linux; Android 13) CustomExtraAyu/1.0"

def _warn(message: str) -> None:
    _log.warning(message)


def download(
    url: str,
    target: str,
    max_bytes: int = MAX_DOWNLOAD_BYTES,
    timeout: int = 20,
) -> Tuple[bool, str]:
    """Download ``url`` into ``target``. Returns ``(ok, error_message)``."""
    url = (url or "").strip()
    if not url:
        return (False, "empty url")
    if not (url.startswith("http://") or url.startswith("https://")):
        return (False, "only http(s) urls are supported")

    files.ensure(os.path.dirname(target))
    temp = target + ".part"
    try:
        import requests  # provided by the SDK runtime
    except Exception as error:
        return (False, "requests unavailable: %s" % error)

    _log.info("download start: %s", _short(url))
    started = os.times().elapsed if hasattr(os, "times") else 0.0
    try:
        with requests.get(url, stream=True, timeout=timeout, headers={"User-Agent": USER_AGENT}) as response:
            if response.status_code != 200:
                return (False, "HTTP %s" % response.status_code)
            declared = response.headers.get("Content-Length")
            if declared is not None:
                try:
                    if int(declared) > max_bytes:
                        return (False, "file is larger than %d MB" % (max_bytes // (1024 * 1024)))
                except (TypeError, ValueError):
                    pass
            written = 0
            with open(temp, "wb") as handle:
                for chunk in response.iter_content(CHUNK):
                    if not chunk:
                        continue
                    written += len(chunk)
                    if written > max_bytes:
                        handle.close()
                        _remove(temp)
                        return (False, "file is larger than %d MB" % (max_bytes // (1024 * 1024)))
                    handle.write(chunk)
        if written == 0:
            _remove(temp)
            return (False, "empty response")
        os.replace(temp, target)
        _log.info("download done: %s, %.1f MB", _short(url), written / (1024.0 * 1024.0))
        return (True, "")
    except Exception as error:
        _remove(temp)
        _warn("download failed for %s: %s" % (url, error))
        return (False, str(error))


def ensure_cached(url: str, force: bool = False) -> Tuple[Optional[str], str]:
    """Return a local path for ``url``, downloading it once."""
    if not url:
        return (None, "empty url")
    target = files.url_cache_path(url)
    if files.exists(target) and not force and files.file_size(target) > 0:
        _log.debug("cache hit: %s", _short(url))
        return (target, "")
    ok, error = download(url, target)
    if not ok:
        return (None, error)
    return (target, "")


def _remove(path_value: str) -> None:
    try:
        if path_value and os.path.exists(path_value):
            os.remove(path_value)
    except Exception:
        pass


def _short(url: str) -> str:
    """Compact URL for logs: host plus the tail of the path."""
    text = url or ""
    if len(text) <= 64:
        return text
    return "%s…%s" % (text[:48], text[-12:])
