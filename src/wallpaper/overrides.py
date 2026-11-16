"""Per-chat wallpaper overrides.

Stored as one small JSON file. Keys are dialog ids, values are partial settings
that shadow the global ones for that chat only.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from core import files, state

FILE_NAME = "overrides.json"


class Overrides:
    def __init__(self) -> None:
        self._data: Dict[str, Dict[str, Any]] = {}
        self.loaded = False

    def load(self) -> None:
        raw = files.read_json(FILE_NAME, {})
        if isinstance(raw, dict):
            self._data = {
                str(key): value
                for key, value in raw.items()
                if isinstance(value, dict)
            }
        else:
            self._data = {}
        self.loaded = True

    def save(self) -> bool:
        return files.write_json(FILE_NAME, self._data)

    # -- access -------------------------------------------------------------
    def get(self, dialog_id: Optional[int]) -> Optional[Dict[str, Any]]:
        if dialog_id is None:
            return None
        return self._data.get(str(dialog_id))

    def set(self, dialog_id: int, data: Dict[str, Any]) -> bool:
        if dialog_id is None:
            return False
        clean = {key: value for key, value in data.items() if value not in (None, "")}
        self._data[str(dialog_id)] = clean
        return self.save()

    def clear(self, dialog_id: int) -> bool:
        if str(dialog_id) in self._data:
            del self._data[str(dialog_id)]
        return self.save()

    def clear_all(self) -> bool:
        self._data.clear()
        return self.save()

    def count(self) -> int:
        return len(self._data)

    def items(self):
        return list(self._data.items())

    def describe(self) -> str:
        return "%d override(s)" % self.count()
