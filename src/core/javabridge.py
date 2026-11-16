"""Single place where Java classes are resolved.

Reflection is the fragile part of any client plugin, so every lookup goes
through here: a missing class is cached once, logged once and reported in the
diagnostics page instead of raising a traceback in a hot path.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

logger: Any = None
_classes: Dict[str, Any] = {}
_missing: Dict[str, bool] = {}
_bound_methods: Dict[str, bool] = {}

CLASS_NAMES = {
    # Android
    "View": "android.view.View",
    "ViewGroup": "android.view.ViewGroup",
    "Context": "android.content.Context",
    "Color": "android.graphics.Color",
    "Bitmap": "android.graphics.Bitmap",
    "BitmapFactory": "android.graphics.BitmapFactory",
    "Canvas": "android.graphics.Canvas",
    "Paint": "android.graphics.Paint",
    "Drawable": "android.graphics.drawable.Drawable",
    "BitmapDrawable": "android.graphics.drawable.BitmapDrawable",
    "ColorDrawable": "android.graphics.drawable.ColorDrawable",
    "GradientDrawable": "android.graphics.drawable.GradientDrawable",
    "BlurMaskFilter": "android.graphics.BlurMaskFilter",
    "BuildVersion": "android.os.Build$VERSION",
    "Intent": "android.content.Intent",
    "Handler": "android.os.Handler",
    "Looper": "android.os.Looper",
    # Telegram / exteraGram
    "ApplicationLoader": "org.telegram.messenger.ApplicationLoader",
    "AndroidUtilities": "org.telegram.messenger.AndroidUtilities",
    "Theme": "org.telegram.ui.ActionBar.Theme",
    "ChatActivity": "org.telegram.ui.ChatActivity",
    "DialogsActivity": "org.telegram.ui.DialogsActivity",
    "LaunchActivity": "org.telegram.ui.LaunchActivity",
    "ChatMessageCell": "org.telegram.ui.Cells.ChatMessageCell",
    "MessageObject": "org.telegram.messenger.MessageObject",
    "BuildVars": "org.telegram.messenger.BuildVars",
    "ExteraConfig": "com.exteragram.messenger.ExteraConfig",
    "MediaPlayer": "android.media.MediaPlayer",
    "SurfaceView": "android.view.SurfaceView",
}


def bind(log: Any = None) -> None:
    global logger
    if log is not None:
        logger = log


def _warn(message: str) -> None:
    if logger is not None:
        try:
            logger.debug("%s", message)
        except Exception:
            pass


def find_class(fqcn: str) -> Optional[Any]:
    """Resolve a class by fully qualified name, caching hits and misses."""
    if fqcn in _classes:
        return _classes[fqcn]
    if fqcn in _missing:
        return None
    java_class = None
    try:
        from hook_utils import find_class as _find_class  # type: ignore

        java_class = _find_class(fqcn)
    except Exception:
        java_class = None
    if java_class is None:
        try:
            from java.lang import Class as JClass  # type: ignore

            java_class = JClass.forName(fqcn)
        except Exception:
            java_class = None
    if java_class is None:
        _missing[fqcn] = True
        _warn("class not found: %s" % fqcn)
        return None
    _classes[fqcn] = java_class
    return java_class


def cls(alias: str) -> Optional[Any]:
    """Resolve a class from :data:`CLASS_NAMES` by short alias."""
    fqcn = CLASS_NAMES.get(alias)
    if not fqcn:
        return None
    return find_class(fqcn)


def has(alias: str) -> bool:
    return cls(alias) is not None


def mark(alias: str, bound: bool) -> None:
    _bound_methods[alias] = bool(bound)


def bindings() -> Dict[str, bool]:
    return dict(_bound_methods)


def android_sdk() -> int:
    try:
        version = cls("BuildVersion")
        if version is None:
            return 0
        return int(version.SDK_INT)
    except Exception:
        return 0


def application_context() -> Optional[Any]:
    try:
        loader = cls("ApplicationLoader")
        if loader is not None:
            context = loader.applicationContext
            if context is not None:
                return context
    except Exception:
        pass
    try:
        from client_utils import get_last_fragment  # type: ignore

        fragment = get_last_fragment()
        if fragment is not None:
            return fragment.getParentActivity() or fragment.getContext()
    except Exception:
        pass
    return None
