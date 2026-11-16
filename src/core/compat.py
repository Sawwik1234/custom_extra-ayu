"""Platform guards.

The plugin targets Android 10 (API 29) and newer. Anything that needs a newer
API is checked here instead of being assumed, and the result is reported in the
diagnostics page.
"""

from __future__ import annotations

from typing import Dict

from core import javabridge

MIN_ANDROID = 29
# Features that need a specific API level.
API_REQUIREMENTS: Dict[str, int] = {
    "blur": 31,          # RenderEffect-based blur
    "surface_control": 29,
    "media_player": 16,
    "bitmap_scaled": 12,
}


def android_version() -> int:
    version = javabridge.android_sdk()
    return version if version else MIN_ANDROID


def supported() -> bool:
    return android_version() >= MIN_ANDROID


def supports(feature: str) -> bool:
    required = API_REQUIREMENTS.get(feature)
    if required is None:
        return True
    return android_version() >= required


def report() -> Dict[str, bool]:
    return {name: supports(name) for name in API_REQUIREMENTS}


def summary() -> str:
    version = android_version()
    state = "supported" if version >= MIN_ANDROID else "too old, expect degraded behaviour"
    return "API %d (%s)" % (version, state)
