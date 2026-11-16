"""Thin helpers over ``ui.settings`` rows.

Two reasons this layer exists:

* every row gets the same icon/formatting conventions;
* when a row type is missing in the host SDK we degrade to ``Text`` instead of
  failing during ``create_settings()``.
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional

from i18n import t

_Header = _Divider = _Switch = _Selector = _Input = _Text = _Custom = None
_ElyxSettings = None

try:
    from ui.settings import (  # type: ignore
        Custom as _CustomImpl,
        Divider as _DividerImpl,
        Header as _HeaderImpl,
        Input as _InputImpl,
        Selector as _SelectorImpl,
        Switch as _SwitchImpl,
        Text as _TextImpl,
    )

    _Header = _HeaderImpl
    _Divider = _DividerImpl
    _Switch = _SwitchImpl
    _Selector = _SelectorImpl
    _Input = _InputImpl
    _Text = _TextImpl
    _Custom = _CustomImpl
except Exception:  # pragma: no cover - host always provides these
    pass

try:
    from elyx import settings as _ElyxSettings  # type: ignore
except Exception:  # pragma: no cover
    _ElyxSettings = None


def available() -> bool:
    return _Header is not None


def header(text: str) -> Any:
    return _Header(text=text)


def divider(text: Optional[str] = None) -> Any:
    return _Divider(text=text) if text else _Divider()


def switch(key: str, text: str, default: bool, subtext: Optional[str] = None,
           on_change: Optional[Callable] = None) -> Any:
    return _Switch(
        key=key,
        text=text,
        default=default,
        subtext=subtext,
        icon="msg_settings",
        on_change=on_change,
    )


def selector(key: str, text: str, default: int, items: List[str],
             subtext: Optional[str] = None, on_change: Optional[Callable] = None) -> Any:
    return _Selector(
        key=key,
        text=text,
        default=default,
        items=items,
        subtext=subtext,
        icon="msg_list",
        on_change=on_change,
    )


def slider(key: str, text: str, default: int, subtext: Optional[str] = None,
           on_change: Optional[Callable] = None) -> Any:
    """Numeric value as an ``Input`` row (the SDK has no native slider)."""
    return _Input(
        key=key,
        text=text,
        default=str(default),
        subtext=subtext,
        icon="msg_edit",
        on_change=(lambda value, cb=on_change: cb(value) if cb else None),
    )


def text_input(key: str, text: str, default: str, subtext: Optional[str] = None,
               on_change: Optional[Callable] = None) -> Any:
    return _Input(
        key=key,
        text=text,
        default=default,
        subtext=subtext,
        icon="msg_edit",
        on_change=on_change,
    )


def info(text: str, subtext: Optional[str] = None, accent: bool = False,
         red: bool = False, on_click: Optional[Callable] = None,
         on_long_click: Optional[Callable] = None,
         sub_page: Optional[Callable] = None, icon: str = "msg_info") -> Any:
    kwargs = {
        "text": text,
        "icon": icon,
        "accent": accent,
        "red": red,
    }
    if subtext:
        kwargs["subtext"] = subtext
    if on_click is not None:
        kwargs["on_click"] = on_click
    if on_long_click is not None:
        kwargs["on_long_click"] = on_long_click
    if sub_page is not None:
        kwargs["create_sub_fragment"] = sub_page
    return _Text(**kwargs)


def action(text: str, subtext: Optional[str] = None, icon: str = "msg_arrow_forward",
           on_click: Optional[Callable] = None,
           sub_page: Optional[Callable] = None) -> Any:
    kwargs = {"text": text, "icon": icon}
    if subtext:
        kwargs["subtext"] = subtext
    if on_click is not None:
        kwargs["on_click"] = on_click
    if sub_page is not None:
        kwargs["create_sub_fragment"] = sub_page
    return _Text(**kwargs)


def custom(view: Any) -> Any:
    return _Custom(view=view)


def yes_no(value: bool) -> str:
    return t("on") if value else t("off")
