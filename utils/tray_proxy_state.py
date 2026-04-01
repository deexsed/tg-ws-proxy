"""Потокобезопасное состояние прокси для трей-иконки."""
from __future__ import annotations

import threading
from typing import Callable, Literal

ProxyPhase = Literal["idle", "starting", "listening", "error", "stopping"]


class ProxyRuntimeState:
    __slots__ = ("_lock", "_phase", "_subscribers")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._phase: ProxyPhase = "idle"
        self._subscribers: list[Callable[[str], None]] = []

    def _notify(self, phase: str) -> None:
        for cb in tuple(self._subscribers):
            try:
                cb(phase)
            except Exception:
                pass

    def subscribe(self, callback: Callable[[str], None]) -> None:
        with self._lock:
            self._subscribers.append(callback)

    def reset_for_start(self) -> None:
        with self._lock:
            self._phase = "starting"
        self._notify("starting")

    def set_listening(self) -> None:
        with self._lock:
            self._phase = "listening"
        self._notify("listening")

    def set_error(self, detail: str) -> None:
        _ = detail
        with self._lock:
            self._phase = "error"
        self._notify("error")

    def set_stopping(self) -> None:
        with self._lock:
            self._phase = "stopping"
        self._notify("stopping")

    def mark_idle_after_thread(self, *, had_exception: bool) -> None:
        with self._lock:
            if had_exception:
                return
            self._phase = "idle"
        self._notify("idle")

    def snapshot(self) -> dict:
        with self._lock:
            return {"phase": self._phase}


