"""Dialogs used by the plugin, with graceful degradation.

``ui.alert.AlertDialogBuilder`` is the preferred path. When it is unavailable the
call is reported through a bulletin and returns ``False``, so callers keep a single
code path.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from ayu_ui.bulletin import bulletin_error, bulletin_info


def _activity() -> Optional[Any]:
    try:
        from client_utils import get_last_fragment  # type: ignore

        fragment = get_last_fragment()
        if fragment is not None:
            activity = fragment.getParentActivity()
            if activity is not None:
                return activity
    except Exception:
        pass
    try:
        from core import javabridge

        return javabridge.application_context()
    except Exception:
        return None


def dialog_choose(
    title: str,
    items: List[str],
    on_pick: Callable[[int], None],
    negative: str = "Cancel",
) -> bool:
    """Show a list dialog; ``on_pick`` receives the chosen index."""
    if not items:
        bulletin_info(title)
        return False
    activity = _activity()
    if activity is None:
        bulletin_error("no activity")
        return False
    try:
        from ui.alert import AlertDialogBuilder  # type: ignore

        builder = AlertDialogBuilder(activity)

        def handle(target: Any, which: int) -> None:
            try:
                on_pick(int(which))
            except Exception:
                pass
            try:
                target.dismiss()
            except Exception:
                pass

        builder.set_title(title)
        builder.set_items(items, handle)
        try:
            builder.set_negative_button(negative)
        except Exception:
            pass
        builder.show()
        return True
    except Exception:
        return False


def dialog_choose_with_cancel(
    title: str,
    items: List[str],
    on_pick: Callable[[int], None],
    on_cancel: Callable[[], None],
    negative: str = "Cancel",
    positive: str = "OK",
) -> bool:
    """Two-step dialog: choose an entry, then confirm or cancel."""
    activity = _activity()
    if activity is None or not items:
        return False
    try:
        from ui.alert import AlertDialogBuilder  # type: ignore

        builder = AlertDialogBuilder(activity)
        builder.set_title(title)
        builder.set_message("\n".join(items))
        builder.set_positive_button(positive, lambda target, _which: _call(on_pick, target))
        builder.set_negative_button(negative, lambda target, _which: _call(on_cancel, target))
        builder.show()
        return True
    except Exception:
        return False


def dialog_message(title: str, message: str, positive: str = "OK") -> bool:
    activity = _activity()
    if activity is None:
        bulletin_info("%s: %s" % (title, message))
        return False
    try:
        from ui.alert import AlertDialogBuilder  # type: ignore

        builder = AlertDialogBuilder(activity)
        builder.set_title(title)
        builder.set_message(message)
        builder.set_positive_button(positive, lambda target, _which: _dismiss(target))
        builder.show()
        return True
    except Exception:
        bulletin_info("%s: %s" % (title, message))
        return False


def _call(callback: Callable[[], None], target: Any) -> None:
    try:
        callback()
    finally:
        _dismiss(target)


def _dismiss(target: Any) -> None:
    try:
        target.dismiss()
    except Exception:
        pass
