"""Skin registry: which logical element maps to which client surface.

A skin is a folder with ``skin.json`` and images named after the elements:

    skins/<skin_id>/skin.json
    skins/<skin_id>/out_bubble.png
    skins/<skin_id>/in_bubble.png
    skins/<skin_id>/panel.png
    skins/<skin_id>/header.png

``skin.json`` may override the image names and tint colors.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import ayu_colors as colors
import ayu_files as files
import ayu_images as images
import ayu_state as state
from ayu_files import write_file
from ayu_log import get as _get_logger

_log = _get_logger("skins.registry")

ELEMENT_OUT = "out_bubble"
ELEMENT_IN = "in_bubble"
ELEMENT_PANEL = "panel"
ELEMENT_HEADER = "header"

ELEMENTS = (ELEMENT_OUT, ELEMENT_IN, ELEMENT_PANEL, ELEMENT_HEADER)

SUPPORTED_EXTENSIONS = ("png", "webp", "jpg", "jpeg")

DEFAULT_SKIN_ID = "default"


class Skin:
    def __init__(self, skin_id: str, folder: str) -> None:
        self.skin_id = skin_id
        self.folder = folder
        self.images: Dict[str, str] = {}
        self.tints: Dict[str, int] = {}
        self._bitmaps: Dict[str, Any] = {}

    # -- loading ------------------------------------------------------------
    def load(self) -> int:
        self.images.clear()
        self.tints.clear()
        self.release()
        meta = files.read_json(os.path.join(self.skin_id, "skin.json"), {})
        if isinstance(meta, dict):
            declared = meta.get("images")
            if isinstance(declared, dict):
                for element, filename in declared.items():
                    if element in ELEMENTS and filename:
                        candidate = os.path.join(self.folder, str(filename))
                        if files.exists(candidate):
                            self.images[element] = candidate
            declared_tints = meta.get("tints")
            if isinstance(declared_tints, dict):
                for element, value in declared_tints.items():
                    parsed = colors.parse(str(value))
                    if element in ELEMENTS and parsed is not None:
                        self.tints[element] = parsed

        for element in ELEMENTS:
            if element in self.images:
                continue
            for ext in SUPPORTED_EXTENSIONS:
                candidate = os.path.join(self.folder, "%s.%s" % (element, ext))
                if files.exists(candidate):
                    self.images[element] = candidate
                    break
        _log.info(
            "skin %s loaded: %d/%d element(s) [%s]",
            self.skin_id,
            len(self.images),
            len(ELEMENTS),
            ", ".join(sorted(self.images.keys())) or "none",
        )
        return len(self.images)

    def has(self, element: str) -> bool:
        return element in self.images

    def bitmap(self, element: str, width: int, height: int) -> Optional[Any]:
        path = self.images.get(element)
        if not path:
            return None
        key = "%s@%dx%d" % (element, width, height)
        if key in self._bitmaps:
            return self._bitmaps[key]
        bitmap = images.decode(path, width, height)
        if bitmap is None:
            return None
        self._bitmaps[key] = bitmap
        return bitmap

    def tint(self, element: str, fallback: Optional[int] = None) -> Optional[int]:
        return self.tints.get(element, fallback)

    def release(self) -> None:
        for bitmap in list(self._bitmaps.values()):
            try:
                if bitmap is not None:
                    bitmap.recycle()
            except Exception:
                pass
        self._bitmaps.clear()


class Registry:
    def __init__(self) -> None:
        self._skins: Dict[str, Skin] = {}
        self.active: Optional[Skin] = None

    # -- discovery ----------------------------------------------------------
    def scan(self) -> List[str]:
        root = files.skins_dir()
        files.ensure(root)
        found: List[str] = []
        try:
            for name in sorted(os.listdir(root)):
                full = os.path.join(root, name)
                if os.path.isdir(full):
                    found.append(name)
        except Exception:
            return []
        return found

    def ensure_default(self) -> str:
        root = files.skins_dir()
        files.ensure(root)
        folder = os.path.join(root, DEFAULT_SKIN_ID)
        files.ensure(folder)
        meta_path = os.path.join(folder, "skin.json")
        if not files.exists(meta_path):
            import json

            files.ensure(folder)
            payload = {
                "name": "Default skin",
                "images": {},
                "tints": {
                    ELEMENT_OUT: "#7C4DFF",
                    ELEMENT_IN: "#212121",
                    ELEMENT_PANEL: "#1B1B1F",
                    ELEMENT_HEADER: "#1B1B1F",
                },
            }
            write_file(meta_path, json.dumps(payload, ensure_ascii=False, indent=2))
        return DEFAULT_SKIN_ID

    # -- activation ---------------------------------------------------------
    def activate(self, skin_id: str) -> int:
        if not skin_id:
            self.deactivate()
            return 0
        folder = os.path.join(files.skins_dir(), skin_id)
        if not files.exists(folder):
            state.note_error("skin folder not found: %s" % skin_id)
            self.deactivate()
            return 0
        skin = Skin(skin_id, folder)
        count = skin.load()
        if not count:
            _log.warning("skin %s has no images yet", skin_id)
        self.active = skin
        self._skins[skin_id] = skin
        state.skin_elements = count
        state.skin_source = skin_id
        return count

    def deactivate(self) -> None:
        if self.active is not None:
            _log.debug("skin deactivated: %s", self.active.skin_id)
            self.active.release()
        self.active = None
        state.skin_elements = 0
        state.skin_source = ""

    def current(self) -> Optional[Skin]:
        return self.active

    def release(self) -> None:
        for skin in list(self._skins.values()):
            skin.release()
        self._skins.clear()
        self.active = None
