from __future__ import annotations

import threading
import time

from .bridge import SDRBridge
from .model import LifecycleState


class WatchdogService:
    def __init__(self, bridge: SDRBridge, timeout_s: float = 2.0, *, clock=time.monotonic, poll_s: float = .1):
        if timeout_s <= 0:
            raise ValueError("watchdog timeout must be positive")
        self.bridge = bridge
        self.timeout_s = float(timeout_s)
        self.clock = clock
        self.poll_s = poll_s
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.recoveries = 0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="source-watchdog", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)
        self._thread = None

    def _run(self) -> None:
        last_blocks = self.bridge.blocks_written
        last_change = self.clock()
        while not self._stop.wait(self.poll_s):
            current = self.bridge.blocks_written
            if current != last_blocks:
                last_blocks = current
                last_change = self.clock()
                continue
            state = self.bridge.state
            expired = state is LifecycleState.RUNNING and self.clock() - last_change >= self.timeout_s
            failed = state is LifecycleState.ERROR
            if expired or failed:
                last_error = str(self.bridge.status().get("last_error") or "")
                if "access violation" in last_error.lower():
                    # Une violation native est un défaut de chargement/API ou
                    # un conflit matériel ; réessayer en boucle aggrave l'état
                    # et peut maintenir le périphérique dans un état indéfini.
                    return
                self.recoveries += 1
                if not self.bridge.recover():
                    return
                last_blocks = self.bridge.blocks_written
                last_change = self.clock()
