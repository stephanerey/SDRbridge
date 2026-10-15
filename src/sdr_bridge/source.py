from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import math
import threading
import time
from typing import Callable

import numpy as np

from .model import (
    DeviceCapabilities,
    DeviceDescriptor,
    Discontinuity,
    RadioConfig,
    SampleFormat,
    TimeDomain,
    TimestampOrigin,
)


@dataclass(frozen=True, slots=True)
class SourceChunk:
    payload: memoryview
    sample_count: int
    first_sample_index: int
    timestamp_ns: int
    time_domain: TimeDomain
    timestamp_origin: TimestampOrigin
    discontinuity: Discontinuity = Discontinuity.NONE
    lost_samples: int | None = 0


BlockCallback = Callable[[SourceChunk], None]
ErrorCallback = Callable[[BaseException], None]


class IQSource(ABC):
    @abstractmethod
    def enumerate(self) -> list[DeviceDescriptor]: ...

    @abstractmethod
    def capabilities(self, device_id: str) -> DeviceCapabilities: ...

    @abstractmethod
    def open(self, device_id: str) -> None: ...

    @abstractmethod
    def configure(self, request: RadioConfig) -> RadioConfig: ...

    @abstractmethod
    def start(self, on_block: BlockCallback, on_error: ErrorCallback | None = None) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @property
    @abstractmethod
    def name(self) -> str: ...


class SimulatedSource(IQSource):
    """Source IQ déterministe conforme au profil de recette S6."""

    DEVICE_ID = "simulated:0"

    def __init__(
        self,
        block_samples: int = 4096,
        tone_hz: float = 10_000.0,
        amplitude: float = 0.25,
        seed: int = 1,
        *,
        realtime: bool = True,
    ):
        if block_samples < 1:
            raise ValueError("block_samples must be positive")
        if not 0.0 <= amplitude <= 1.0:
            raise ValueError("amplitude must be in [0, 1]")
        self.block_samples = int(block_samples)
        self.tone_hz = float(tone_hz)
        self.amplitude = float(amplitude)
        self.seed = int(seed)
        self.realtime = bool(realtime)
        self._rng = np.random.default_rng(seed)
        self._config = RadioConfig()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._phase = 0.0
        self._first_sample_index = 0
        self._opened = False
        self._on_block: BlockCallback | None = None
        self._on_error: ErrorCallback | None = None
        self._faults: dict[int, tuple[str, int | None]] = {}

    @property
    def name(self) -> str:
        return "Deterministic simulated source"

    def enumerate(self) -> list[DeviceDescriptor]:
        return [DeviceDescriptor(self.DEVICE_ID, "simulated", self.name, serial="seed-1")]

    def capabilities(self, device_id: str) -> DeviceCapabilities:
        if device_id != self.DEVICE_ID:
            raise KeyError(device_id)
        return DeviceCapabilities(
            device_id=device_id,
            frequency_ranges_hz=((1_000, 2_000_000_001),),
            sample_rates_sps=(96_000, 192_000, 2_000_000),
            bandwidths_hz=(96_000, 192_000, 1_536_000, 2_000_000),
            antennas=("SIM",),
            gain_ranges={"amplitude": (0.0, 1.0)},
            agc_available=False,
            formats=(SampleFormat.CS16, SampleFormat.CF32),
        )

    def open(self, device_id: str = DEVICE_ID) -> None:
        if device_id != self.DEVICE_ID:
            raise KeyError(device_id)
        self._opened = True

    def configure(self, request: RadioConfig) -> RadioConfig:
        if not self._opened:
            raise RuntimeError("source is not open")
        request.validate()
        self._config = request
        return request

    def apply_config(self, config: RadioConfig) -> None:
        self.configure(config)

    def inject_fault(self, block_sequence: int, kind: str, lost_samples: int | None = None) -> None:
        if kind not in {"known_gap", "unknown_gap", "exception", "stall"}:
            raise ValueError("unknown simulated fault")
        self._faults[int(block_sequence)] = (kind, lost_samples)

    def start(self, on_block, on_error: ErrorCallback | BlockCallback | None = None) -> None:
        # Compatibilité de source amont : start(config, callback).
        if isinstance(on_block, RadioConfig):
            config = on_block
            callback = on_error
            if callback is None:
                raise TypeError("legacy start requires callback")
            if not self._opened:
                self.open()
            self.configure(config)

            def legacy(chunk: SourceChunk) -> None:
                callback(chunk.payload, chunk.sample_count)  # type: ignore[misc]

            on_block = legacy
            on_error = None
        if self._thread and self._thread.is_alive():
            raise RuntimeError("source already started")
        if not self._opened:
            raise RuntimeError("source is not open")
        self._on_block = on_block
        self._on_error = on_error if callable(on_error) else None
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="iq-simulator", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=2.0)
            if thread.is_alive():
                raise RuntimeError("simulated source thread did not stop")
        self._thread = None

    def close(self) -> None:
        self.stop()
        self._opened = False

    def _payload(self, phases: np.ndarray) -> memoryview:
        complex_iq = self.amplitude * (np.cos(phases) + 1j * np.sin(phases))
        if self._config.sample_format is SampleFormat.CF32:
            return memoryview(complex_iq.astype("<c8", copy=False)).cast("B")
        values = np.empty((len(phases), 2), dtype="<i2")
        scaled = np.rint(np.stack((complex_iq.real, complex_iq.imag), axis=1) * 32768.0)
        values[:] = np.clip(scaled, -32768, 32767).astype("<i2")
        return memoryview(values).cast("B")

    def _run(self) -> None:
        next_deadline = time.perf_counter()
        block_sequence = 0
        try:
            while not self._stop.is_set():
                fault = self._faults.pop(block_sequence, None)
                if fault:
                    kind, amount = fault
                    if kind == "exception":
                        raise RuntimeError("injected simulated source failure")
                    if kind == "stall":
                        self._stop.wait(0.05)
                        block_sequence += 1
                        continue
                    gap = amount if kind == "known_gap" else self.block_samples
                    self._first_sample_index += int(gap or self.block_samples)
                    discontinuity = Discontinuity.SOURCE_LOSS
                    lost = int(gap) if kind == "known_gap" and gap is not None else None
                else:
                    discontinuity = Discontinuity.START if block_sequence == 0 else Discontinuity.NONE
                    lost = 0
                cfg = self._config
                n = self.block_samples
                omega = 2.0 * math.pi * self.tone_hz / cfg.sample_rate_sps
                phases = self._phase + omega * np.arange(n, dtype=np.float64)
                payload = self._payload(phases)
                timestamp = time.monotonic_ns()
                chunk = SourceChunk(
                    payload=payload,
                    sample_count=n,
                    first_sample_index=self._first_sample_index,
                    timestamp_ns=timestamp,
                    time_domain=TimeDomain.HOST_MONOTONIC,
                    timestamp_origin=TimestampOrigin.HOST_OBSERVATION,
                    discontinuity=discontinuity,
                    lost_samples=lost,
                )
                if self._on_block:
                    self._on_block(chunk)
                self._first_sample_index += n
                self._phase = float((self._phase + omega * n) % (2.0 * math.pi))
                block_sequence += 1
                if self.realtime:
                    next_deadline += n / cfg.sample_rate_sps
                    delay = next_deadline - time.perf_counter()
                    if delay > 0:
                        self._stop.wait(delay)
                    elif delay < -0.5:
                        next_deadline = time.perf_counter()
        except BaseException as exc:
            if self._on_error and not self._stop.is_set():
                self._on_error(exc)
