"""Loads ``locales/strings_<lang>.yml`` when the host provides YAML.

The plugin keeps a dictionary fallback in :mod:`i18n`, so a missing PyYAML or an
unreadable locale file never blocks loading: the built-in strings win and the
problem is reported once in the log.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import ayu_files as files
from ayu_log import get as _get_logger

_log = _get_logger("core.l10n")

LOCALES_DIR_NAME = "locales"


def _locales_dir() -> str:
    """Locales ship next to ``main.py``; walk up from this module."""
    here = os.path.dirname(os.path.abspath(__file__))
    for _ in range(4):
        candidate = os.path.join(here, LOCALES_DIR_NAME)
        if files.exists(candidate):
            return candidate
        here = os.path.dirname(here)
    return ""


def _load_yaml(path_value: str) -> Optional[Dict[str, str]]:
    try:
        import yaml  # type: ignore
    except Exception:
        return None
    raw = files.read_file(path_value)
    if not raw:
        return None
    try:
        data = yaml.safe_load(raw)
    except Exception as error:
        _log.warning("cannot parse %s: %s", path_value, error)
        return None
    if not isinstance(data, dict):
        return None
    return {str(key): str(value) for key, value in data.items() if isinstance(value, (str, int, float))}


def available_locales() -> Dict[str, str]:
    folder = _locales_dir()
    result: Dict[str, str] = {}
    if not folder:
        return result
    for name, full in sorted(files.list_files(folder, ("yml", "yaml", "json")).items()):
        if name.startswith("strings_"):
            result[name[len("strings_"):]] = full
    return result


def load(lang: str) -> Dict[str, str]:
    """Return merged overrides for ``lang`` on top of English."""
    merged: Dict[str, str] = {}
    locales = available_locales()
    for code in ("en", lang):
        path_value = locales.get(code)
        if not path_value:
            continue
        data = _load_yaml(path_value)
        if data:
            merged.update(data)
            _log.debug("locale %s: %d string(s)", code, len(data))
    return merged
