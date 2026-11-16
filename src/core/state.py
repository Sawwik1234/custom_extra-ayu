"""Runtime state shared by the engine, the renderers and the settings pages.

Kept tiny on purpose: counters, the last error string and the current render
state. Nothing here is persisted except through :mod:`core.prefs`.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

STATE_RUNNING = "running"
STATE_PAUSED = "paused"
STATE_OFF = "off"

hook_events = 0
last_error: Optional[str] = None
render_state = STATE_OFF
active_kind = ""
attached_screens = 0
skin_elements = 0
skin_source = ""

# Result of the reflection probe, filled by ``wallpaper.attach``.
hooks: Dict[str, bool] = {}


def note_error(message: str) -> None:
    global last_error
    last_error = message or "unknown error"


def clear_error() -> None:
    global last_error
    last_error = None


def count_hook_event() -> int:
    global hook_events
    hook_events += 1
    return hook_events


def set_render(new_state: str, kind: str = "") -> None:
    global render_state, active_kind
    render_state = new_state
    active_kind = kind


def snapshot() -> Dict[str, Any]:
    return {
        "hook_events": hook_events,
        "last_error": last_error,
        "render_state": render_state,
        "active_kind": active_kind,
        "attached_screens": attached_screens,
        "skin_elements": skin_elements,
        "skin_source": skin_source,
        "hooks": dict(hooks),
    }
