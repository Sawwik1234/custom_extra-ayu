"""Background sources: built-in palettes, files and URLs, plus decoding.

Gradients and particles need no files at all, so the plugin works out of the box
without shipping megabytes of media. Files and URLs are resolved to a local path
and decoded once, at screen size, through :class:`core.images`.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import ayu_colors as colors
import ayu_files as files
import ayu_javabridge as javabridge
import ayu_net as net
import ayu_prefs as prefs

# Built-in gradient palettes: (name, stop colors, animation style).
BUILTIN_GRADIENTS: List[Tuple[str, Tuple[str, str, str], str]] = [
    ("ayu_aurora", ("#0B1026", "#1B3A6B", "#4A2C8F"), "drift"),
    ("ayu_sunset", ("#2B1055", "#7B2D8E", "#FF6B6B"), "drift"),
    ("ayu_neon", ("#0D0221", "#2D1B69", "#00E5FF"), "pulse"),
    ("ayu_forest", ("#061A12", "#0F3D2E", "#4CAF83"), "drift"),
    ("ayu_ember", ("#1A0B0B", "#5B1E1E", "#FF9A3C"), "pulse"),
    ("ayu_ocean", ("#011C2B", "#064663", "#41B3C7"), "drift"),
    ("ayu_mono", ("#0A0A0A", "#1F1F1F", "#3D3D3D"), "static"),
]

BUILTIN_NAMES: List[str] = [item[0] for item in BUILTIN_GRADIENTS]

IMAGE_EXTENSIONS = ("png", "jpg", "jpeg", "webp", "bmp")
VIDEO_EXTENSIONS = ("mp4", "webm", "mkv", "gif", "m4v", "3gp")


def gradient_by_name(name: str) -> Tuple[Tuple[str, str, str], str]:
    for entry in BUILTIN_GRADIENTS:
        if entry[0] == name:
            return (entry[1], entry[2])
    return (BUILTIN_GRADIENTS[0][1], BUILTIN_GRADIENTS[0][2])


def is_video(path_value: str) -> bool:
    return files.extension(path_value) in VIDEO_EXTENSIONS


def is_image(path_value: str) -> bool:
    return files.extension(path_value) in IMAGE_EXTENSIONS


def resolve_local(prefs_obj: prefs.Prefs) -> Tuple[Optional[str], str]:
    """Return the local media path for the selected source.

    Built-in palettes return ``(None, "")`` — they are drawn procedurally.
    """
    source = prefs_obj.text("wallpaper_source")
    if source == prefs.SOURCE_BUILTIN:
        return (None, "")
    if source == prefs.SOURCE_URL:
        url = prefs_obj.text("wallpaper_url")
        if not url:
            return (None, "url is empty")
        cached, error = net.ensure_cached(url)
        if not cached:
            return (None, error or "download failed")
        return (cached, "")
    if source == prefs.SOURCE_FILE:
        picked = prefs_obj.text("wallpaper_file")
        if not picked:
            return (None, "no file selected")
        if not files.exists(picked):
            return (None, "selected file is gone")
        return (picked, "")
    return (None, "unknown source")


def refresh_source(prefs_obj: prefs.Prefs, force_download: bool = False) -> Tuple[Optional[str], str]:
    """Resolve the current source, forcing a re-download when asked."""
    if force_download and prefs_obj.text("wallpaper_source") == prefs.SOURCE_URL:
        url = prefs_obj.text("wallpaper_url")
        if url:
            cached, error = net.ensure_cached(url, force=True)
            if cached:
                return (cached, "")
            return (None, error or "download failed")
    return resolve_local(prefs_obj)


def adopt_picked_file(source_path: str) -> Optional[str]:
    """Copy a user-picked file into the plugin cache and return its path."""
    if not source_path or not files.exists(source_path):
        return None
    copied = files.copy_to_cache(source_path, prefix="picked")
    return copied


def gradient_colors(prefs_obj: prefs.Prefs) -> List[int]:
    """Resolved stop colors, taking the tint from the palette or the theme."""
    stops, _style = gradient_by_name(prefs_obj.text("wallpaper_builtin"))
    parsed = [colors.parse(stop, 0xFF000000) or 0xFF000000 for stop in stops]
    accent = colors.parse(prefs_obj.text("theme_accent"))
    if accent is not None:
        parsed[1] = colors.mix(parsed[1], accent, 0.35)
    return parsed


def gradient_style(prefs_obj: prefs.Prefs) -> str:
    _stops, style = gradient_by_name(prefs_obj.text("wallpaper_builtin"))
    return style


def available_builtins() -> Dict[str, str]:
    """Names for the selector, kept short and translatable in the UI."""
    return {name: name for name in BUILTIN_NAMES}


def describe_source(prefs_obj: prefs.Prefs, local_path: Optional[str]) -> str:
    source = prefs_obj.text("wallpaper_source")
    if source == prefs.SOURCE_BUILTIN:
        return "builtin:%s" % prefs_obj.text("wallpaper_builtin")
    if source == prefs.SOURCE_URL:
        return "url:%s" % prefs_obj.text("wallpaper_url")
    if local_path:
        return "file:%s" % os.path.basename(local_path)
    return source or "unknown"


def media_kind_of(prefs_obj: prefs.Prefs, local_path: Optional[str]) -> str:
    if local_path is None:
        return prefs.KIND_GRADIENT
    return "video" if is_video(local_path) else "image"
