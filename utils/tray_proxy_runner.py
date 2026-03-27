"""Запуск asyncio-прокси в отдельном потоке (общий для tray entrypoints)."""
from __future__ import annotations

import asyncio as _asyncio
import threading
import time
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

import proxy.tg_ws_proxy as tg_ws_proxy

ProxyStopState = Tuple[Any, Any]  # (loop, Event)


class ProxyThreadRunner:
    """Управляет потоком с tg_ws_proxy._run и корректной остановкой."""

    def __init__(
        self,
        *,
        default_config: Mapping[str, Any],
        get_config: Callable[[], Dict[str, Any]],
        log: Any,
        show_error: Callable[[str], None],
        join_timeout: float = 2.0,
        warn_on_join_stuck: bool = False,
        treat_win_error_10048_as_port_in_use: bool = False,
    ) -> None:
        self._default = dict(default_config)
        self._get_config = get_config
        self._log = log
        self._show_error = show_error
        self._join_timeout = join_timeout
        self._warn_on_join_stuck = warn_on_join_stuck
        self._win10048 = treat_win_error_10048_as_port_in_use

        self._thread: Optional[threading.Thread] = None
        self._async_stop: Optional[ProxyStopState] = None

    @property
    def async_stop(self) -> Optional[ProxyStopState]:
        return self._async_stop

    def _run_proxy_thread(
        self,
        port: int,
        dc_opt: Dict[int, str],
        verbose: bool,
        host: str = "127.0.0.1",
    ) -> None:
        loop = _asyncio.new_event_loop()
        _asyncio.set_event_loop(loop)
        stop_ev = _asyncio.Event()
        self._async_stop = (loop, stop_ev)

        try:
            loop.run_until_complete(
                tg_ws_proxy._run(port, dc_opt, stop_event=stop_ev, host=host)
            )
        except Exception as exc:
            self._log.error("Proxy thread crashed: %s", exc)
            msg = str(exc)
            port_busy = "Address already in use" in msg
            if self._win10048 and "10048" in msg:
                port_busy = True
            if port_busy:
                self._show_error(
                    "Не удалось запустить прокси:\n"
                    "Порт уже используется другим приложением.\n\n"
                    "Закройте приложение, использующее этот порт, "
                    "или измените порт в настройках прокси и перезапустите."
                )
        finally:
            loop.close()
            self._async_stop = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            self._log.info("Proxy already running")
            return

        cfg = self._get_config()
        port = cfg.get("port", self._default["port"])
        host = cfg.get("host", self._default["host"])
        dc_ip_list = cfg.get("dc_ip", self._default["dc_ip"])
        verbose = bool(cfg.get("verbose", False))

        try:
            dc_opt = tg_ws_proxy.parse_dc_ip_list(dc_ip_list)
        except ValueError as e:
            self._log.error("Bad config dc_ip: %s", e)
            self._show_error(f"Ошибка конфигурации:\n{e}")
            return

        self._log.info("Starting proxy on %s:%d ...", host, port)

        buf_kb = cfg.get("buf_kb", self._default["buf_kb"])
        pool_size = cfg.get("pool_size", self._default["pool_size"])
        tg_ws_proxy._RECV_BUF = max(4, buf_kb) * 1024
        tg_ws_proxy._SEND_BUF = tg_ws_proxy._RECV_BUF
        tg_ws_proxy._WS_POOL_SIZE = max(0, pool_size)

        self._thread = threading.Thread(
            target=self._run_proxy_thread,
            args=(port, dc_opt, verbose, host),
            daemon=True,
            name="proxy",
        )
        self._thread.start()

    def stop(self) -> None:
        if self._async_stop:
            loop, stop_ev = self._async_stop
            loop.call_soon_threadsafe(stop_ev.set)
            if self._thread:
                self._thread.join(timeout=self._join_timeout)
                if self._warn_on_join_stuck and self._thread.is_alive():
                    self._log.warning(
                        "Proxy thread did not finish within timeout; "
                        "the process may still exit shortly"
                    )
        self._thread = None
        self._log.info("Proxy stopped")

    def restart(self) -> None:
        self._log.info("Restarting proxy...")
        self.stop()
        time.sleep(0.3)
        self.start()
