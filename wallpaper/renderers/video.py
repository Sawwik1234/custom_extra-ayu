"""Video / GIF loop background.

Decoding and playback stay entirely on the Java side: ``MediaPlayer`` renders
into a ``SurfaceView``. Python only starts, stops and reconfigures it, so the
frame cost in the interpreter is zero.

If a surface or player cannot be created (old device, unsupported codec), the
host falls back to the gradient renderer.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from core import files, javabridge
from core.log import get as _get_logger
from wallpaper.renderers.base import Renderer

_log = _get_logger("wallpaper.renderers.video")


class VideoRenderer(Renderer):
    kind = "video"

    def __init__(self) -> None:
        super().__init__()
        self.path = ""
        self.looping = True
        self.muted = True
        self.dim = 0
        self._player: Optional[Any] = None
        self._surface_view: Optional[Any] = None
        self._holder_listener: Optional[Any] = None

    def configure(self, settings: Dict[str, Any]) -> None:
        super().configure(settings)
        self.path = str(settings.get("path") or "")
        self.looping = bool(settings.get("looping", True))
        self.muted = bool(settings.get("muted", True))
        self.dim = int(settings.get("dim") or 0)

    # -- lifecycle ----------------------------------------------------------
    def attach_view(self, container: Any, width: int, height: int) -> Optional[Any]:
        """Create the SurfaceView, start playback and return the view."""
        if not self.path or not files.exists(self.path):
            return None
        surface_class = javabridge.cls("SurfaceView")
        player_class = javabridge.cls("MediaPlayer")
        if surface_class is None or player_class is None or container is None:
            return None

        _log.info("starting video background: %s", files.extension(self.path) or "video")
        try:
            view = surface_class(container.getContext())
            try:
                view.setZOrderOnTop(False)
                view.setZOrderMediaOverlay(True)
            except Exception:
                pass
            self._surface_view = view
            self._start_player(player_class, view)
            return view
        except Exception as error:
            self._note("video attach failed: %s" % error)
            return None

    def _start_player(self, player_class: Any, view: Any) -> None:
        player = player_class()
        player.setDataSource(self.path)
        if self.looping:
            player.setLooping(True)
        if self.muted:
            player.setVolume(0.0, 0.0)

        holder = view.getHolder()
        try:
            player.setDisplay(holder)
        except Exception:
            pass

        try:
            player.prepare()
        except Exception:
            try:
                player.prepareAsync()
            except Exception as error:
                self._note("video prepare failed: %s" % error)
                self._release_player()
                return

        try:
            player.start()
        except Exception as error:
            self._note("video start failed: %s" % error)
            self._release_player()
            return

        self._player = player
        _log.info("video background playing (looping=%s, muted=%s)", self.looping, self.muted)

    def draw(self, canvas: Any, width: int, height: int, delta: float) -> bool:
        # Playback is handled by the platform; the shared scheduler only keeps
        # the dimming overlay alive.
        if self._player is None:
            return False
        self.advance(delta)
        return True

    def overlay_dim(self, canvas: Any, width: int, height: int) -> bool:
        """Draw the dimming layer above the surface."""
        if self.dim <= 0 or canvas is None:
            return True
        paint = self.paint()
        if paint is None:
            return True
        try:
            paint.setShader(None)
            paint.setColor(0xFF000000)
            paint.setAlpha(int(255 * min(100, self.dim) / 100))
            canvas.drawRect(0.0, 0.0, float(width), float(height), paint)
            return True
        except Exception:
            return True

    def pause(self) -> None:
        if self._player is None:
            return
        try:
            if self._player.isPlaying():
                self._player.pause()
        except Exception:
            pass

    def resume(self) -> None:
        if self._player is None:
            return
        try:
            self._player.start()
        except Exception:
            pass

    def _release_player(self) -> None:
        player = self._player
        self._player = None
        if player is None:
            return
        try:
            self._player and player.stop()
        except Exception:
            pass
        try:
            player.release()
        except Exception:
            pass

    def release(self) -> None:
        if self._player is not None:
            _log.debug("video background released")
        self._release_player()
        self._surface_view = None
        self._holder_listener = None
        super().release()

    def _note(self, message: str) -> None:
        _log.warning(message)
