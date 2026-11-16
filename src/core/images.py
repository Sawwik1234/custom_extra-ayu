"""Bitmap decoding with a small bounded cache.

Everything returned here is a Java ``Bitmap``; the plugin never keeps raw pixel
buffers in Python, so memory stays in native allocations the GC can free.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from core import colors, files, javabridge

MAX_CACHE_ENTRIES = 3

_cache: Dict[str, Any] = {}
_order: list = []


def _bitmap_factory() -> Optional[Any]:
    return javabridge.cls("BitmapFactory")


def decode_bounds(path_value: str) -> Tuple[int, int]:
    factory = _bitmap_factory()
    if factory is None or not files.exists(path_value):
        return (0, 0)
    try:
        options = factory.Options()
        options.inJustDecodeBounds = True
        factory.decodeFile(path_value, options)
        return (int(options.outWidth), int(options.outHeight))
    except Exception:
        return (0, 0)


def decode(path_value: str, max_width: int, max_height: int) -> Optional[Any]:
    """Decode ``path_value`` downscaled to fit the given box."""
    factory = _bitmap_factory()
    if factory is None or not files.exists(path_value):
        return None

    key = "%s@%dx%d" % (path_value, max_width, max_height)
    if key in _cache:
        return _cache[key]

    try:
        options = factory.Options()
        options.inJustDecodeBounds = True
        factory.decodeFile(path_value, options)
        width = int(options.outWidth)
        height = int(options.outHeight)
        if width <= 0 or height <= 0:
            return None

        sample = 1
        while (width // (sample * 2)) >= max(1, max_width) and (height // (sample * 2)) >= max(1, max_height):
            sample *= 2

        options = factory.Options()
        options.inSampleSize = sample
        options.inPreferredConfig = factory.Config.RGB_565
        bitmap = factory.decodeFile(path_value, options)
        if bitmap is None:
            return None
        bitmap = scale_to_fill(bitmap, max_width, max_height)
        _remember(key, bitmap)
        return bitmap
    except Exception as error:
        if javabridge.logger is not None:
            javabridge.logger.warning("decode failed: %s" % error)
        return None


def scale_to_fill(bitmap: Any, max_width: int, max_height: int) -> Any:
    """Scale down to fit the box while keeping the aspect ratio."""
    try:
        width = int(bitmap.getWidth())
        height = int(bitmap.getHeight())
        if width <= 0 or height <= 0:
            return bitmap
        ratio = min(float(max_width) / width, float(max_height) / height)
        if ratio >= 1.0:
            return bitmap
        new_width = max(1, int(width * ratio))
        new_height = max(1, int(height * ratio))
        scaled = bitmap.copy(bitmap.getConfig(), True)
        scaled = javabridge.cls("Bitmap").createScaledBitmap(bitmap, new_width, new_height, True)
        try:
            bitmap.recycle()
        except Exception:
            pass
        return scaled
    except Exception:
        return bitmap


def _remember(key: str, bitmap: Any) -> None:
    if key not in _cache:
        _order.append(key)
    _cache[key] = bitmap
    while len(_order) > MAX_CACHE_ENTRIES:
        oldest = _order.pop(0)
        old = _cache.pop(oldest, None)
        if old is not None and old is not bitmap:
            try:
                old.recycle()
            except Exception:
                pass


def clear_cache() -> None:
    for key in list(_order):
        bitmap = _cache.pop(key, None)
        try:
            if bitmap is not None:
                bitmap.recycle()
        except Exception:
            pass
    _order.clear()


def average_color(bitmap: Any, step: int = 16) -> Optional[int]:
    """Cheap average color, used to derive an accent from a photo."""
    if bitmap is None:
        return None
    try:
        width = int(bitmap.getWidth())
        height = int(bitmap.getHeight())
        if width <= 0 or height <= 0:
            return None
        red = green = blue = 0
        samples = 0
        y = 0
        while y < height:
            x = 0
            while x < width:
                pixel = int(bitmap.getPixel(x, y))
                red += (pixel >> 16) & 0xFF
                green += (pixel >> 8) & 0xFF
                blue += pixel & 0xFF
                samples += 1
                x += step
            y += step
        if samples == 0:
            return None
        return 0xFF000000 | ((red // samples) << 16) | ((green // samples) << 8) | (blue // samples)
    except Exception:
        return None


def tinted_color(bitmap: Any, fallback: int = 0xFF7C4DFF) -> int:
    value = average_color(bitmap)
    if value is None:
        return fallback
    if colors.luminance(value) < 0.12:
        return colors.lighten(value, 0.45)
    return value
