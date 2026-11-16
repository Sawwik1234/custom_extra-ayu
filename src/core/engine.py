"""Frame scheduler shared by every animated background.

Design notes (the "keep it cheap" part):

* one Java ``Runnable`` per attached screen, no Python threads;
* the frame budget is computed once per tick and reused;
* idle detection, background pausing and scroll pausing are pure flag checks;
* nothing is allocated per frame except what the renderer itself needs.

Renderers implement a tiny protocol:

    prepare(width, height) -> None
    draw(canvas, width, height, frame_seconds) -> None
    release() -> None
"""

from __future__ import annotations

import time
from typing import Any, List, Optional

from core import state

logger: Any = None


def bind(log: Any = None) -> None:
    global logger
    if log is not None:
        logger = log


class Scheduler:
    """Drives :meth:`RunnableHost.draw_frame` at a capped frame rate."""

    def __init__(self) -> None:
        self._hosts: List[Any] = []
        self._posted = False
        self._last_tick = 0.0
        self._running = False
        self._backgrounded = False
        self._global_pause = False
        self._fps_limit = 30
        self._idle_enabled = True
        self._idle_delay = 15.0
        self._last_interaction = 0.0
        self._last_error = ""

    # -- configuration ------------------------------------------------------
    def configure(
        self,
        fps_limit: int,
        idle_enabled: bool,
        idle_delay: int,
        background_pause: bool,
    ) -> None:
        self._fps_limit = max(15, min(60, int(fps_limit)))
        self._idle_enabled = bool(idle_enabled)
        self._idle_delay = max(0, int(idle_delay))
        self._backgrounded = False if not background_pause else self._backgrounded

    # -- lifecycle ----------------------------------------------------------
    def add(self, host: Any) -> None:
        if host not in self._hosts:
            self._hosts.append(host)
        self.resume()

    def remove(self, host: Any) -> None:
        try:
            self._hosts.remove(host)
        except ValueError:
            pass
        if not self._hosts:
            self._running = False

    def stop_all(self) -> None:
        for host in list(self._hosts):
            try:
                host.release_renderer()
            except Exception:
                pass
        self._hosts.clear()
        self._running = False
        self._posted = False
        state.set_render(state.STATE_OFF)

    # -- pause sources ------------------------------------------------------
    def set_global_pause(self, paused: bool) -> None:
        self._global_pause = bool(paused)
        if not paused:
            self._last_interaction = time.monotonic()

    def set_backgrounded(self, backgrounded: bool) -> None:
        self._backgrounded = bool(backgrounded)

    def note_interaction(self) -> None:
        self._last_interaction = time.monotonic()

    def resume(self) -> None:
        self._last_interaction = time.monotonic()
        if self._running:
            return
        self._running = True
        self._schedule(0)

    # -- tick ---------------------------------------------------------------
    def _is_idle(self) -> bool:
        if not self._idle_enabled or self._idle_delay <= 0:
            return False
        return (time.monotonic() - self._last_interaction) > self._idle_delay

    def _schedule(self, delay_ms: int) -> None:
        if self._posted or not self._running:
            return
        try:
            from android_utils import run_on_ui_thread  # type: ignore

            run_on_ui_thread(self._tick, delay_ms)
            self._posted = True
        except Exception as error:
            self._posted = False
            self._log_once("scheduler unavailable: %s" % error)
            self._running = False

    def _tick(self) -> None:
        self._posted = False
        if not self._running or not self._hosts:
            self._running = False
            state.set_render(state.STATE_OFF)
            return

        now = time.monotonic()
        interval = 1.0 / float(self._fps_limit)

        if self._backgrounded or self._global_pause or self._is_idle():
            state.set_render(state.STATE_PAUSED)
            # Keep polling cheaply so we can resume without a new trigger.
            self._schedule(int(interval * 1000 * 4) or 250)
            return

        delta = now - self._last_tick if self._last_tick else interval
        self._last_tick = now
        if delta > 0.25:
            delta = interval  # after a long pause, do not jump the animation

        state.set_render(state.STATE_RUNNING)
        alive = 0
        for host in tuple(self._hosts):
            try:
                host.draw_frame(delta)
                alive += 1
            except Exception as error:
                self._log_once("frame error: %s" % error)
                self.remove(host)
        if not alive:
            self._running = False
            state.set_render(state.STATE_OFF)
            return

        self._schedule(int(interval * 1000))

    def _log_once(self, message: str) -> None:
        if message == self._last_error:
            return
        self._last_error = message
        state.note_error(message)
        if logger is not None:
            try:
                logger.warning("%s", message)
            except Exception:
                pass


scheduler = Scheduler()


def shutdown() -> None:
    scheduler.stop_all()
