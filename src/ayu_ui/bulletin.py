"""Bulletin wrappers that never raise.

The settings callbacks run on the UI thread and a bulletin failure must not break
the action the user asked for, so everything here is best-effort.
"""

from __future__ import annotations

from typing import Any, Optional

try:
    from ui.bulletin import BulletinHelper  # type: ignore
except Exception:  # pragma: no cover
    BulletinHelper = None

try:
    from android_utils import copy_to_clipboard  # type: ignore
except Exception:  # pragma: no cover
    copy_to_clipboard = None


def _show(method: str, *args: Any) -> bool:
    if BulletinHelper is None:
        return False
    handler = getattr(BulletinHelper, method, None)
    if handler is None:
        return False
    try:
        handler(*args)
        return True
    except Exception:
        return False


def bulletin_info(message: str) -> bool:
    return _show("show_info", message)


def bulletin_error(message: str) -> bool:
    return _show("show_error", message)


def bulletin_success(message: str) -> bool:
    return _show("show_success", message)


def clipboard(text: str) -> bool:
    if copy_to_clipboard is None:
        return False
    try:
        copy_to_clipboard(text)
        return True
    except Exception:
        return False


def dialog_choose(title: str, items: Any, on_pick: Any, negative: str = "Cancel") -> bool:
    """Re-exported here so pages import a single UI module."""
    from ayu_ui import dialogs

    return dialogs.dialog_choose(title, list(items), on_pick, negative)


def dialog_message(title: str, message: str) -> bool:
    from ayu_ui import dialogs

    return dialogs.dialog_message(title, message)
