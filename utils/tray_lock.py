"""Один экземпляр tray-приложения: lock-файлы с PID и метаданными."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Callable, Optional

import psutil
import sys

SameProcessFn = Callable[[dict, psutil.Process], bool]


def make_same_process_checker(
    *,
    script_marker: Optional[str],
    frozen_match: Callable[[psutil.Process], bool],
) -> SameProcessFn:
    """Проверка «наш ли процесс» для lock-файла (cmdline + frozen)."""

    def check(lock_meta: dict, proc: psutil.Process) -> bool:
        try:
            lock_ct = float(lock_meta.get("create_time", 0.0))
            proc_ct = float(proc.create_time())
            if lock_ct > 0 and abs(lock_ct - proc_ct) > 1.0:
                return False
        except Exception:
            return False

        if script_marker is not None:
            try:
                for arg in proc.cmdline():
                    if script_marker in arg:
                        return True
            except Exception:
                pass

        frozen = bool(getattr(sys, "frozen", False))
        if frozen:
            return frozen_match(proc)

        return False

    return check


def frozen_match_executable_basename(proc: psutil.Process) -> bool:
    import os as _os

    return _os.path.basename(sys.executable).lower() == proc.name().lower()


def frozen_match_app_name_contains(app_name: str) -> Callable[[psutil.Process], bool]:
    needle = app_name.lower()

    def _m(proc: psutil.Process) -> bool:
        return needle in proc.name().lower()

    return _m


class SingleInstanceLock:
    """RAII-совместимый lock каталога приложения (*.lock с PID)."""

    def __init__(
        self,
        app_dir: Path,
        same_process: SameProcessFn,
        *,
        log: Optional[logging.Logger] = None,
    ) -> None:
        self._app_dir = app_dir
        self._same_process = same_process
        self._log = log
        self._lock_file: Optional[Path] = None

    @property
    def lock_file(self) -> Optional[Path]:
        return self._lock_file

    def acquire(self) -> bool:
        self._app_dir.mkdir(parents=True, exist_ok=True)
        for f in self._app_dir.glob("*.lock"):
            pid = None
            meta: dict = {}
            try:
                pid = int(f.stem)
            except Exception:
                f.unlink(missing_ok=True)
                continue

            try:
                raw = f.read_text(encoding="utf-8").strip()
                if raw:
                    meta = json.loads(raw)
            except Exception:
                meta = {}

            try:
                proc = psutil.Process(pid)
                if self._same_process(meta, proc):
                    return False
            except Exception:
                pass

            f.unlink(missing_ok=True)

        lock_file = self._app_dir / f"{os.getpid()}.lock"
        try:
            proc = psutil.Process(os.getpid())
            payload = {"create_time": proc.create_time()}
            lock_file.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            lock_file.touch()

        self._lock_file = lock_file
        return True

    def release(self) -> None:
        if not self._lock_file:
            return
        try:
            self._lock_file.unlink(missing_ok=True)
        except Exception:
            if self._log:
                self._log.debug("Lock release failed", exc_info=True)
        self._lock_file = None
