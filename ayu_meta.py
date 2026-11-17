"""Plugin metadata and small YAML helpers.

The Elyx plugin base class (``elyxcore._plugin.ElyxPlugin``) does **not** provide
``getName()`` or ``version``: those belong to the legacy single-file plugin
convention, where ``__name__`` / ``__version__`` were plain module constants that
the host patched onto the instance. An Elyx plugin is constructed as
``plugin_class(plugin_id, plugin_path)`` and keeps its identity in
``metainfo.yml`` instead.

This module reads that file once and exposes:

* ``metainfo()``  - the parsed mapping (empty dict when missing or broken);
* ``text(key)``   - a single value as ``str``;
* ``yaml_load()`` - a tiny parser covering the flat ``key: value`` files used
  by the SDK (``metainfo.yml``, ``locales/*.yml``).

PyYAML is used when the runtime happens to ship it; the fallback keeps the
plugin independent from it, because a missing import here would break loading.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import ayu_files as files
from ayu_log import get as _get_logger

_log = _get_logger("meta")

METainfo_NAME = "metainfo.yml"

_cache: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Minimal YAML subset: flat mappings, quoted strings, comments, [a, b] lists,
# block lists ("- item"), booleans and numbers. Enough for metainfo and locales.
# ---------------------------------------------------------------------------
def _strip_comment(line: str) -> str:
    quote = ""
    for index, char in enumerate(line):
        if quote:
            if char == quote and line[index - 1] != "\\":
                quote = ""
        elif char in ("'", '"'):
            quote = char
        elif char == "#":
            return line[:index]
    return line


def _scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        inner = value[1:-1]
        if value[0] == '"':
            inner = inner.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")
        else:
            inner = inner.replace("''", "'")
        return inner
    lowered = value.lower()
    if lowered in ("true", "yes", "on"):
        return True
    if lowered in ("false", "no", "off"):
        return False
    if lowered in ("null", "none", "~"):
        return None
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_scalar(part) for part in inner.split(",")]
    try:
        if "." in value:
            return float(value)
        return int(value)
    except (TypeError, ValueError):
        return value


def yaml_load(text: str) -> Dict[str, Any]:
    """Parse the flat YAML used by SDK files. Unknown shapes are skipped."""
    data: Dict[str, Any] = {}
    if not text:
        return data
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(text)
        if isinstance(loaded, dict):
            return loaded
    except Exception:
        pass

    key_of_block_list: Optional[str] = None
    for raw_line in text.splitlines():
        line = _strip_comment(raw_line).rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        if stripped.startswith("- "):
            if key_of_block_list is not None:
                data.setdefault(key_of_block_list, [])
                if isinstance(data[key_of_block_list], list):
                    data[key_of_block_list].append(_scalar(stripped[2:]))
            continue
        if ":" not in stripped:
            continue
        key, raw_value = stripped.split(":", 1)
        key = key.strip()
        if not key:
            continue
        if raw_value.strip():
            data[key] = _scalar(raw_value)
            key_of_block_list = None
        else:
            data[key] = ""
            key_of_block_list = key
    return data


# ---------------------------------------------------------------------------
# Metainfo
# ---------------------------------------------------------------------------
def _candidate_paths() -> List[str]:
    names = ("metainfo.yml", "metainfo.yaml", "metainfo.json")
    locations: List[str] = []
    here = os.path.abspath(os.path.dirname(__file__) if "__file__" in globals() else ".")
    for folder in (here, files.root() or ""):
        if not folder:
            continue
        for name in names:
            candidate = os.path.join(folder, name)
            if candidate not in locations:
                locations.append(candidate)
    return locations


def metainfo(reload: bool = False) -> Dict[str, Any]:
    """Parsed metainfo of this plugin; ``{}`` when it cannot be read."""
    global _cache
    if _cache is not None and not reload:
        return _cache
    data: Dict[str, Any] = {}
    for candidate in _candidate_paths():
        try:
            if not os.path.isfile(candidate):
                continue
            with open(candidate, "r", encoding="utf-8") as handle:
                raw = handle.read()
        except Exception as error:
            _log.debug("cannot read %s: %s", candidate, error)
            continue
        if candidate.endswith(".json"):
            try:
                import json

                loaded = json.loads(raw)
                data = loaded if isinstance(loaded, dict) else {}
            except Exception as error:
                _log.warning("cannot parse %s: %s", candidate, error)
                data = {}
        else:
            data = yaml_load(raw)
        if data:
            break
    if not data:
        _log.warning("metainfo not found near %s", os.path.dirname(__file__))
    _cache = data
    return data


def text(key: str, default: str = "") -> str:
    value = metainfo().get(key)
    if value is None or value == "":
        return default
    return str(value)


def name(default: str = "Custom Extra Ayu") -> str:
    return text("name", default)


def version(default: str = "0.0.0") -> str:
    return text("version", default)


def plugin_id(default: str = "custom_extra_ayu") -> str:
    return text("id", default)


def sdk_requirement() -> str:
    return text("sdk_version")


def app_requirement() -> str:
    return text("app_version")
