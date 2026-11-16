"""The animated background host.

Two modes are supported, chosen at runtime by what the client exposes:

1. **Drawable mode** (preferred) — a generated Java ``Drawable`` is installed as
   the background of the chat's own background view. The client keeps its layout
   and z-order, our code only paints.
2. **View mode** (fallback) — a custom ``View`` is inserted into the screen and
   covers it from behind.

In both modes the drawing entry point is a single method that talks to a
renderer. Nothing here allocates per frame.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from core import engine, state
from core.log import get as _get_logger
from wallpaper.renderers import Renderer, create, settings_for
from wallpaper.renderers.video import VideoRenderer

_peer_counter = 0
_log = _get_logger("wallpaper.host")


class WallpaperHost:
    """Owns one renderer bound to one screen."""

    def __init__(self, prefs_obj: Any, kind: str, local_path: Optional[str] = None) -> None:
        self.prefs = prefs_obj
        self.kind = kind
        self.local_path = local_path
        self.renderer: Optional[Renderer] = None
        self.view: Optional[Any] = None
        self.drawable_peer: Optional[Any] = None
        self.attached = False
        self.width = 0
        self.height = 0
        self.alpha = 255
        self._fallback_color = 0xFF101014
        self._last_frame = 0.0

    # -- setup --------------------------------------------------------------
    def build(self) -> None:
        with _log.timed("build renderer %s" % self.kind):
            self._build_renderer()

    def _build_renderer(self) -> None:
        self.renderer = create(self.kind)
        settings = settings_for(self.prefs, self.kind, self.local_path, self._fallback_color)
        try:
            self.renderer.configure(settings)
        except Exception as error:
            self._note("renderer configure failed: %s" % error)

    def attach(self, width: int, height: int) -> None:
        if self.renderer is None:
            self.build()
        if self.renderer is None:
            return
        self.width = max(1, int(width))
        self.height = max(1, int(height))
        try:
            self.renderer.prepare(self.width, self.height)
        except Exception as error:
            self._note("renderer prepare failed: %s" % error)
        self.attached = True
        _log.debug("host attached %s %dx%d", self.kind, self.width, self.height)
        engine.scheduler.add(self)

    # -- attaching to a live screen ----------------------------------------
    def create_view(self, context: Any) -> Optional[Any]:
        """Build the view the screen should show.

        Video goes through a real ``SurfaceView`` (decoding stays native); every
        other renderer uses a drawable-painting view. ``None`` means "nothing to
        insert, fall back to the drawable path".
        """
        if context is None or self.renderer is None:
            return None
        if isinstance(self.renderer, VideoRenderer):
            view = self.renderer.attach_view(context, self.width or 1080, self.height or 1920)
            if view is not None:
                self.view = view
                return view
            self._note("video unavailable, falling back to gradient")
            self._switch_to_gradient()
            return None
        peer = build_view(self, context)
        if peer is None:
            return None
        self.view = peer
        return peer

    def _switch_to_gradient(self) -> None:
        from wallpaper.renderers import GradientRenderer

        self.renderer = GradientRenderer()
        try:
            self.renderer.configure(settings_for(self.prefs, "gradient", self.local_path, self._fallback_color))
            self.renderer.prepare(self.width or 1080, self.height or 1920)
        except Exception as error:
            self._note("gradient fallback failed: %s" % error)

    @property
    def needs_view(self) -> bool:
        return isinstance(self.renderer, VideoRenderer)

    def detach(self) -> None:
        self.attached = False
        engine.scheduler.remove(self)
        if self.renderer is not None:
            try:
                self.renderer.release()
            except Exception:
                pass
        _log.debug("host detached %s", self.kind)
        self.renderer = None
        self.view = None
        self.drawable_peer = None

    # -- frame --------------------------------------------------------------
    def draw_frame(self, delta: float) -> None:
        if not self.attached or self.renderer is None:
            return
        self._last_frame = delta
        if self.view is not None:
            try:
                self.view.invalidate()
            except Exception:
                pass

    def overlay(self, canvas: Any, width: int, height: int) -> None:
        """Draw the dimming layer above a video surface."""
        if isinstance(self.renderer, VideoRenderer):
            try:
                self.renderer.overlay_dim(canvas, width, height)
            except Exception:
                pass

    def render(self, canvas: Any, width: int, height: int) -> bool:
        """Called from the Java ``draw`` callback."""
        if self.renderer is None:
            return False
        if width != self.width or height != self.height:
            self.width = max(1, int(width))
            self.height = max(1, int(height))
            try:
                self.renderer.prepare(self.width, self.height)
            except Exception:
                pass
        try:
            return bool(self.renderer.draw(canvas, self.width, self.height, self._last_frame or 0.016))
        except Exception as error:
            _log.once("render-%s" % self.kind, "render failed (%s): %s", self.kind, error)
            return False

    def target_size(self) -> tuple:
        if self.view is not None:
            try:
                return (int(self.view.getWidth()), int(self.view.getHeight()))
            except Exception:
                pass
        return (self.width or 1080, self.height or 1920)

    def _note(self, message: str) -> None:
        state.note_error(message)
        _log.warning(message)


def build_video_overlay(host: WallpaperHost) -> Optional[Any]:
    """Transparent view that paints dimming on top of the video surface."""
    try:
        from extera_utils.classes import Base, java_subclass, joverload  # type: ignore
        from android.view import View  # type: ignore
    except Exception as error:
        host._note("class proxy unavailable for overlay: %s" % error)
        return None
    try:

        @java_subclass(View)
        class VideoDimOverlay(Base):
            @joverload("onDraw", ["android.graphics.Canvas"])
            def on_draw(self, canvas):
                try:
                    host.overlay(canvas, self.getWidth(), self.getHeight())
                except Exception:
                    pass

        return VideoDimOverlay
    except Exception as error:
        host._note("overlay proxy failed: %s" % error)
        return None


def build_drawable(host: WallpaperHost) -> Optional[Any]:
    """Create the Java ``Drawable`` that paints ``host``.

    Returns the Python peer (``.java`` for the Java object) or ``None`` when the
    class proxy API is unavailable.
    """
    global _peer_counter
    try:
        from extera_utils.classes import Base, java_subclass, joverload  # type: ignore
        from android.graphics.drawable import Drawable  # type: ignore
    except Exception as error:
        host._note("class proxy unavailable: %s" % error)
        return None

    try:

        @java_subclass(Drawable)
        class AnimatedBackground(Base):
            @joverload("draw", ["android.graphics.Canvas"])
            def draw_canvas(self, canvas):
                try:
                    bounds = self.getBounds()
                    width = bounds.width() if bounds is not None else host.width
                    height = bounds.height() if bounds is not None else host.height
                    host.render(canvas, width, height)
                except Exception:
                    pass

            @joverload("setAlpha", ["int"])
            def set_alpha(self, value):
                try:
                    host.alpha = int(value)
                except Exception:
                    pass

            @joverload("setColorFilter", ["android.graphics.ColorFilter"])
            def set_color_filter(self, _filter):
                return None

            @joverload("getOpacity", [])
            def get_opacity(self):
                return -1  # PixelFormat.TRANSLUCENT

            @joverload("invalidateSelf", [])
            def invalidate_self(self):
                try:
                    super().invalidate_self()
                except Exception:
                    pass
                try:
                    if host.view is not None:
                        host.view.invalidate()
                except Exception:
                    pass

        peer = AnimatedBackground.new_instance()
        _peer_counter += 1
        return peer
    except Exception as error:
        host._note("drawable proxy failed: %s" % error)
        return None


def build_view(host: WallpaperHost, context: Any) -> Optional[Any]:
    """Fallback path: a plain custom ``View`` that paints ``host``."""
    if context is None:
        return None
    try:
        from extera_utils.classes import Base, java_subclass, joverload  # type: ignore
        from android.view import View  # type: ignore
    except Exception as error:
        host._note("class proxy unavailable for view: %s" % error)
        return None

    try:

        @java_subclass(View)
        class AnimatedBackgroundView(Base):
            @joverload("onDraw", ["android.graphics.Canvas"])
            def on_draw(self, canvas):
                try:
                    if host.render(canvas, self.getWidth(), self.getHeight()):
                        return
                except Exception:
                    pass
                try:
                    canvas.drawColor(host._fallback_color)
                except Exception:
                    pass

        return AnimatedBackgroundView.new_instance(context)
    except Exception as error:
        host._note("view proxy failed: %s" % error)
        return None
