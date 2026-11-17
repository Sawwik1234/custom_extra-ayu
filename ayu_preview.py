"""Settings-page preview of a theme.

Drawn with plain Android views once per bind, never animated: the preview must
cost nothing while the settings page is open.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import ayu_colors as colors; import ayu_javabridge as javabridge


def _dp(value: int) -> int:
    try:
        from org.telegram.messenger import AndroidUtilities as AU  # type: ignore

        return int(AU.dp(value))
    except Exception:
        return int(value * 2)


def _rounded_drawable(fill: int, radius_dp: int, stroke: Optional[int] = None) -> Any:
    gradient = javabridge.cls("GradientDrawable")
    if gradient is None:
        return javabridge.cls("ColorDrawable")(int(fill)) if javabridge.cls("ColorDrawable") else None
    try:
        drawable = gradient()
        drawable.setShape(0)  # RECTANGLE
        drawable.setColor(int(fill) & 0xFFFFFFFF)
        drawable.setCornerRadius(float(_dp(radius_dp)))
        if stroke is not None:
            drawable.setStroke(_dp(1), int(stroke) & 0xFFFFFFFF)
        return drawable
    except Exception:
        return None


def create_view(context: Any) -> Optional[Any]:
    """Build the preview container; returns ``None`` when views are unavailable."""
    if context is None:
        return None
    try:
        from android.view import Gravity  # type: ignore
        from android.widget import LinearLayout, TextView  # type: ignore
    except Exception:
        return None
    try:
        layout = LinearLayout(context)
        layout.setOrientation(1)
        layout.setPadding(_dp(12), _dp(12), _dp(12), _dp(12))
        layout.setTag("ayu_theme_preview")
        header = TextView(context)
        header.setText("Custom Extra Ayu")
        header.setTag("ayu_preview_header")
        layout.addView(header)
        incoming = TextView(context)
        incoming.setText("Preview message")
        incoming.setTag("ayu_preview_in")
        layout.addView(incoming)
        outgoing = TextView(context)
        outgoing.setText("Outgoing message")
        outgoing.setTag("ayu_preview_out")
        layout.addView(outgoing)
        return layout
    except Exception:
        return None


def render_into(view: Any, item: Dict[str, Any]) -> None:
    """Paint the theme colors onto an existing preview container."""
    if view is None:
        return
    try:
        page = colors.parse(str(item.get("page_color") or ""), 0xFF101014) or 0xFF101014
        out_bubble = colors.parse(str(item.get("out_bubble") or ""), 0xFF7C4DFF) or 0xFF7C4DFF
        in_bubble = colors.parse(str(item.get("in_bubble") or ""), 0xFF212121) or 0xFF212121
        header = colors.parse(str(item.get("header_color") or ""), 0xFF1B1B1F) or 0xFF1B1B1F

        view.setBackground(_rounded_drawable(page, 12))

        for index in range(view.getChildCount()):
            child = view.getChildAt(index)
            tag = child.getTag()
            if tag == "ayu_preview_header":
                child.setBackground(_rounded_drawable(header, 8))
                child.setTextColor(colors.readable_text(header))
            elif tag == "ayu_preview_in":
                child.setBackground(_rounded_drawable(in_bubble, 14))
                child.setTextColor(colors.readable_text(in_bubble))
            elif tag == "ayu_preview_out":
                child.setBackground(_rounded_drawable(out_bubble, 14))
                child.setTextColor(colors.readable_text(out_bubble))
    except Exception:
        pass
