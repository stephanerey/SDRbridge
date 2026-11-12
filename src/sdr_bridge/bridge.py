from __future__ import annotations

from dataclasses import replace
import logging
import os
import queue
import threading
import time
import uuid
from typing import Callable
from dataclasses import dataclass

import numpy as np

from .model import (
    ClientStats,
    Discontinuity,
    IQBlock,
    LifecycleState,
    RadioConfig,
    StreamProfile,
)
from .profiles import PipelinePool, ProfileRegistry
from .dsp import StreamingRationalResampler
from .ring import RingReader, SharedIQRing
from .source import IQSource, SourceChunk


logger = logging.getLogger(__name__)


class StaleConfigError(RuntimeError):
    code = "STALE_CONFIG"


@dataclass(slots=True)
class _ProfileRing:
    ring: SharedIQRing
    pipeline_token: str
    clients: int = 0


class SDRBridge:
    """Autorité RX unique et orchestrateur sans dépendance Qt."""

    def __init__(
        self,
        source: IQSource,
        config: RadioConfig | None = None,
        *,
        block_samples: int = 4096,
        slots: int = 64,
        source_queue_blocks: int = 256,
        dsp_queue_blocks: int = 512,
        max_clients: int | None = None,
        source_id: str = "source-0",
        device_id: str | None = None,
        run_id: str | None = None,
    ):
        self.source = source
        self.config = config or RadioConfig()
        self.config.validate()
        if max_clients is not None and max_clients <= 0:
            raise ValueError("max_clients must be null or positive")
        if source_queue_blocks <= 0:
            raise ValueError("source_queue_blocks must be positive")
        if dsp_queue_blocks <= 0:
            raise ValueError("dsp_queue_blocks must be positive")
        self.max_clients = max_clients
        self.source_id = source_id
        self.device_id = device_id
        self.run_id = run_id or str(uuid.uuid4())
        self.ring = SharedIQRing(slots, block_samples, sample_format=self.config.sample_format, source_id=source_id)
        self.profiles = ProfileRegistry()
        for output_rate in (192_000, 96_000):
            if output_rate < self.config.sample_rate_sps:
                # Warm the exact multistage design used at runtime.  The old
                # monolithic-FIR prewarm was both expensive and different from
                # the optimized fractional path actually serving clients.
                StreamingRationalResampler(self.config.sample_rate_sps, output_rate)
        self._pipelines = PipelinePool(
            source_id,
            self.config.sample_rate_sps,
            self.config.sample_format,
            parallel_workers=min(4, os.cpu_count() or 1),
        )
        self._clients: dict[str, ClientStats] = {}
        self._client_profile_keys: dict[str, tuple[str, int] | None] = {}
        self._profile_rings: dict[tuple[str, int], _ProfileRing] = {}
        self._lock = threading.RLock()
        self._command_lock = threading.RLock()
        self._state = LifecycleState.IDLE
        self._last_error: str | None = None
        self._epoch = 0
        self._sequence = 0
        self._first_sample_index = 0
        self._source_queue: queue.Queue[tuple[SourceChunk, RadioConfig, int]] = queue.Queue(maxsize=source_queue_blocks)
        self._dsp_queue: queue.Queue[IQBlock] = queue.Queue(maxsize=dsp_queue_blocks)
        self.source_queue_capacity = int(source_queue_blocks)
        self.dsp_queue_capacity = int(dsp_queue_blocks)
        self.source_queue_high_water = 0
        self._dispatch_stop = threading.Event()
        self._dispatch_thread: threading.Thread | None = None
        self._dsp_stop = threading.Event()
        self._dsp_thread: threading.Thread | None = None
        self._recovery_cancel = threading.Event()
        self._pending_source_drops = 0
        self._pending_dsp_drops = 0
        self._closed = False
        self.started_ns = 0
        self.blocks_received = 0
        self.samples_received = 0
        self.blocks_written = 0
        self.samples_written = 0
        self.source_queue_drops = 0
        self.source_losses = 0
        self.source_errors = 0
        self._next_drop_log_at = 0.0
        self.dispatch_processing_seconds = 0.0
        self.dispatch_processing_max_ms = 0.0
        self.dispatch_slow_blocks = 0
        self._next_slow_dispatch_log_at = 0.0
        self.dsp_queue_drops = 0
        self.dsp_queue_high_water = 0
        self.dsp_blocks_processed = 0
        self.dsp_processing_seconds = 0.0
        self.dsp_processing_max_ms = 0.0
        self.dsp_slow_blocks = 0
        self.dsp_errors = 0
        self._next_slow_dsp_log_at = 0.0
        self._next_dsp_drop_log_at = 0.0
        self._rate_interval_ns = 500_000_000
        self._rate_interval_started_ns = 0
        self._rate_interval_samples = 0
        self._rate_last_write_ns = 0
        self._sample_rate_measured = 0.0

    def _reset_rate_measurement_locked(self) -> None:
        self._rate_interval_started_ns = 0
        self._rate_interval_samples = 0
        self._rate_last_write_ns = 0
        self._sample_rate_measured = 0.0

    def _update_rate_measurement_locked(self, sample_count: int, now_ns: int) -> None:
        # A short completed interval reflects the current acquisition rate.
        # The former samples_written / time-since-start value was a cumulative
        # average and could take minutes to converge after a 2 -> 10 MS/s
        # reconfiguration.
        if self._rate_interval_started_ns == 0:
            self._rate_interval_started_ns = now_ns
            self._rate_interval_samples = 0
        self._rate_interval_samples += int(sample_count)
        self._rate_last_write_ns = now_ns
        elapsed_ns = now_ns - self._rate_interval_started_ns
        if elapsed_ns >= self._rate_interval_ns:
            self._sample_rate_measured = self._rate_interval_samples * 1_000_000_000.0 / elapsed_ns
            self._rate_interval_started_ns = now_ns
            self._rate_interval_samples = 0

    @property
    def state(self) -> LifecycleState:
        with self._lock:
            return self._state

    @property
    def running(self) -> bool:
        return self.state is LifecycleState.RUNNING

    @property
    def epoch(self) -> int:
        with self._lock:
            return self._epoch

    def enumerate_devices(self) -> list[dict]:
        return [item.to_dict() for item in self.source.enumerate()]

    def capabilities(self, device_id: str | None = None) -> dict:
        selected = device_id or self.device_id or self.source.enumerate()[0].device_id
        return self.source.capabilities(selected).to_dict()

    @staticmethod
    def _config_for_device(source: IQSource, device_id: str, config: RadioConfig) -> RadioConfig:
        """Drop a device-specific wire choice when the new SDR cannot use it."""
        if config.wire_format is None:
            return config
        formats = source.capabilities(device_id).wire_formats
        if any(value.lower() == config.wire_format.lower() for value in formats):
            return config
        return replace(config, wire_format=None)

    def select_device(self, device_id: str) -> None:
        """Switch the selected backend device, preserving RX when possible."""
        with self._command_lock:
            if device_id == self.device_id:
                return
            running = self.running
            if running:
                self.stop()
            self.source.close()
            self.source.open(device_id)
            request = self._config_for_device(self.source, device_id, self.config)
            effective = self.source.configure(request)
            with self._lock:
                self.device_id = device_id
                self.config = effective
                self._epoch += 1
                # ``sequence`` is the publication cursor of the persistent
                # SDBR ring.  Readers (including the ExtIO and ANTRACK
                # adapters) keep their next cursor across a device switch, so
                # moving it backwards would make them wait until the new
                # producer catches up with the retired sequence.
                self._first_sample_index = 0
            if running:
                self.start()

    def replace_source(
        self,
        source: IQSource,
        device_id: str,
        requested_config: RadioConfig | None = None,
    ) -> RadioConfig:
        """Replace the active RX source while preserving rings and clients."""
        with self._command_lock:
            previous_source = self.source
            previous_device = self.device_id
            previous_config = self.config
            was_running = self.running
            if self.state not in {LifecycleState.IDLE, LifecycleState.READY}:
                self.stop()
            request = replace(
                requested_config or previous_config,
                revision=previous_config.revision + 1,
            )
            try:
                source.open(device_id)
                request = self._config_for_device(source, device_id, request)
                effective = source.configure(request)
                if effective.sample_format is not self.ring.sample_format:
                    raise ValueError(
                        f"source format {effective.sample_format.value} is incompatible with "
                        f"the active {self.ring.sample_format.value} ring"
                    )
                self._pipelines.reconfigure(effective.sample_rate_sps, effective.sample_format)
            except Exception:
                try:
                    source.close()
                finally:
                    if was_running:
                        self.start()
                raise

            try:
                previous_source.close()
            except Exception:
                self._pipelines.reconfigure(previous_config.sample_rate_sps, previous_config.sample_format)
                source.close()
                self.source = previous_source
                self.device_id = previous_device
                if was_running:
                    with self._lock:
                        self._state = LifecycleState.IDLE
                    self.open()
                    self.start()
                raise

            self._clear_source_queue()
            with self._lock:
                self.source = source
                self.device_id = device_id
                self.config = effective
                self._epoch += 1
                self._first_sample_index = 0
                self._state = LifecycleState.READY
                self._last_error = None
            if was_running:
                self.start()
            return effective

    def open(self) -> None:
        with self._command_lock:
            with self._lock:
                if self._state is not LifecycleState.IDLE:
                    if self._state is LifecycleState.READY:
                        return
                    raise RuntimeError(f"cannot open from {self._state.value}")
                self._state = LifecycleState.OPENING
            try:
                devices = self.source.enumerate()
                selected = self.device_id or (devices[0].device_id if devices else None)
                if selected is None:
                    raise RuntimeError("no source device available")
                self.source.open(selected)
                effective = self.source.configure(self.config)
                with self._lock:
                    self.device_id = selected
                    self.config = effective
                    self._state = LifecycleState.READY
                    self._last_error = None
            except Exception as exc:
                with self._lock:
                    self._state = LifecycleState.ERROR
                    self._last_error = str(exc)
                raise

    def _start_dispatcher(self) -> None:
        self._dsp_stop.clear()
        self._dsp_thread = threading.Thread(target=self._dsp_loop, name="sdr-dsp", daemon=True)
        self._dsp_thread.start()
        self._dispatch_stop.clear()
        self._dispatch_thread = threading.Thread(target=self._dispatch_loop, name="sdr-dispatch", daemon=True)
        self._dispatch_thread.start()

    def start(self) -> None:
        with self._command_lock:
            if self._state is LifecycleState.IDLE:
                self.open()
            with self._lock:
                if self._state is LifecycleState.RUNNING:
                    raise RuntimeError("source already started")
                if self._state is not LifecycleState.READY:
                    raise RuntimeError(f"cannot start from {self._state.value}")
                self._state = LifecycleState.STARTING
                self._epoch += 1
                # The epoch and sample index describe the new continuity
                # interval; the ring publication sequence remains monotone
                # for already attached readers.
                self._first_sample_index = 0
                self.started_ns = time.monotonic_ns()
                self._reset_rate_measurement_locked()
                self._recovery_cancel.clear()
            self._start_dispatcher()
            try:
                self.source.start(self._on_source_chunk, self._on_source_error)
            except Exception as exc:
                self._stop_dispatcher()
                with self._lock:
                    self._state = LifecycleState.ERROR
                    self._last_error = str(exc)
                raise
            with self._lock:
                self._state = LifecycleState.RUNNING

    def _stop_dispatcher(self) -> None:
        self._dispatch_stop.set()
        thread = self._dispatch_thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=2.0)
            if thread.is_alive():
                raise RuntimeError("dispatch thread did not stop")
        self._dispatch_thread = None
        self._dsp_stop.set()
        dsp_thread = self._dsp_thread
        if dsp_thread and dsp_thread is not threading.current_thread():
            dsp_thread.join(timeout=2.0)
            if dsp_thread.is_alive():
                raise RuntimeError("DSP thread did not stop")
        self._dsp_thread = None

    def _clear_source_queue(self) -> None:
        for pending in (self._source_queue, self._dsp_queue):
            while True:
                try:
                    pending.get_nowait()
                    pending.task_done()
                except queue.Empty:
                    break

    def stop(self) -> None:
        self._recovery_cancel.set()
        with self._command_lock:
            with self._lock:
                if self._state in (LifecycleState.IDLE, LifecycleState.READY):
                    return
                if self._state is LifecycleState.STOPPING:
                    return
                self._state = LifecycleState.STOPPING
            error: BaseException | None = None
            try:
                self.source.stop()
            except BaseException as exc:
                error = exc
            try:
                self._stop_dispatcher()
            except BaseException as exc:
                error = error or exc
            with self._lock:
                if error:
                    self._state = LifecycleState.ERROR
                    self._last_error = str(error)
                else:
                    self._state = LifecycleState.READY
            if error:
                raise error

    def recover(self, delays=(1.0, 2.0, 5.0, 10.0, 30.0), wait: Callable[[float], bool] | None = None) -> bool:
        wait = wait or self._recovery_cancel.wait
        with self._command_lock:
            with self._lock:
                if self._state not in (LifecycleState.RUNNING, LifecycleState.ERROR):
                    return False
                self._state = LifecycleState.RECOVERING
            try:
                self.source.stop()
            except Exception:
                pass
            try:
                self._stop_dispatcher()
            except Exception:
                pass
            last_error = "recovery failed"
            for delay in delays:
                if wait(float(delay)) or self._recovery_cancel.is_set():
                    with self._lock:
                        self._state = LifecycleState.READY
                    return False
                try:
                    self.source.close()
                    self.source.open(self.device_id)
                    effective = self.source.configure(self.config)
                    with self._lock:
                        self.config = effective
                        self._epoch += 1
                        # Keep the persistent ring cursor monotone across a
                        # backend recovery.  Network encoders own their
                        # separate, epoch-local packet counters.
                        self._first_sample_index = 0
                        self._pipelines.reconfigure(effective.sample_rate_sps, effective.sample_format)
                    self._start_dispatcher()
                    self.source.start(self._on_source_chunk, self._on_source_error)
                    with self._lock:
                        self._state = LifecycleState.RUNNING
                        self._last_error = None
                    return True
                except Exception as exc:
                    last_error = str(exc)
                    try:
                        self._stop_dispatcher()
                    except Exception:
                        pass
            with self._lock:
                self._state = LifecycleState.ERROR
                self._last_error = last_error
            return False

    def close(self) -> None:
        if self._closed:
            return
        try:
            self.stop()
        finally:
            try:
                self.source.close()
            finally:
                for shared in list(self._profile_rings.values()):
                    self._pipelines.unsubscribe(shared.pipeline_token)
                    shared.ring.close(unlink=True)
                self._profile_rings.clear()
                self._pipelines.close()
                self.ring.close(unlink=True)
                self._closed = True
                with self._lock:
                    self._state = LifecycleState.IDLE

    def _on_source_chunk(self, chunk: SourceChunk) -> None:
        # Le callback ne fait qu'une copie possédée et un enqueue borné.
        if chunk.payload_format not in {"CS8", "CS16"}:
            if chunk.release is not None:
                chunk.release(chunk.release_token)
            self._on_source_error(ValueError(f"unsupported source payload format: {chunk.payload_format}"))
            return
        can_transfer = chunk.payload_format == "CS8" and chunk.release is not None
        owned = SourceChunk(
            payload=chunk.payload if can_transfer else memoryview(bytes(chunk.payload)),
            sample_count=chunk.sample_count,
            first_sample_index=chunk.first_sample_index,
            timestamp_ns=chunk.timestamp_ns,
            time_domain=chunk.time_domain,
            timestamp_origin=chunk.timestamp_origin,
            discontinuity=chunk.discontinuity,
            lost_samples=chunk.lost_samples,
            payload_format=chunk.payload_format,
            release=chunk.release if can_transfer else None,
            release_token=chunk.release_token if can_transfer else None,
        )
        if chunk.release is not None and not can_transfer:
            chunk.release(chunk.release_token)
        with self._lock:
            if chunk.discontinuity is Discontinuity.REPLAY_SEEK or (
                chunk.discontinuity is Discontinuity.SOURCE_LOSS and chunk.lost_samples is None
            ):
                self._epoch += 1
                # A seek or unknown source loss starts a new epoch, but the
                # shared-ring publication cursor must never move backwards.
                self._first_sample_index = 0
            if chunk.discontinuity is Discontinuity.SOURCE_LOSS:
                self.source_losses += 1
            config, epoch = self.config, self._epoch
            self.blocks_received += 1
            self.samples_received += chunk.sample_count
        try:
            self._source_queue.put_nowait((owned, config, epoch))
            depth = self._source_queue.qsize()
            with self._lock:
                self.source_queue_high_water = max(self.source_queue_high_water, depth)
        except queue.Full:
            if owned.release is not None:
                owned.release(owned.release_token)
            now = time.monotonic()
            with self._lock:
                self.source_queue_drops += 1
                self._pending_source_drops += chunk.sample_count
                total_drops = self.source_queue_drops
                should_log = total_drops == 1 or now >= self._next_drop_log_at
                if should_log:
                    self._next_drop_log_at = now + 5.0
                    epoch = self._epoch
                    high_water = self.source_queue_high_water
            if should_log:
                logger.warning(
                    "source queue is full; newest block was dropped",
                    extra={
                        "code": "SOURCE_QUEUE_DROP",
                        "run_id": self.run_id,
                        "source_id": self.source_id,
                        "epoch": str(epoch),
                        "details": {
                            "dropped_blocks_total": total_drops,
                            "queue_capacity_blocks": self.source_queue_capacity,
                            "queue_high_water_blocks": high_water,
                        },
                    },
                )

    def _on_source_error(self, exc: BaseException) -> None:
        with self._lock:
            self.source_errors += 1
            self._last_error = str(exc)
            self._state = LifecycleState.ERROR
        logger.error(
            "source reported an acquisition error",
            exc_info=(type(exc), exc, exc.__traceback__),
            extra={
                "code": "SOURCE_ERROR",
                "run_id": self.run_id,
                "source_id": self.source_id,
                "epoch": str(self.epoch),
            },
        )

    def _dispatch_loop(self) -> None:
        while not self._dispatch_stop.is_set() or not self._source_queue.empty():
            try:
                chunk, config, epoch = self._source_queue.get(timeout=0.05)
            except queue.Empty:
                continue
            # Après une commande RF, des blocs produits juste avant l'appel
            # peuvent encore se trouver dans la file. Ils ne doivent pas
            # retarder l'apparition du nouveau centre de fréquence : l'epoch
            # les invalide sans réinitialiser la séquence du ring.
            with self._lock:
                current_epoch = self._epoch
            if epoch != current_epoch:
                if chunk.release is not None:
                    chunk.release(chunk.release_token)
                self._source_queue.task_done()
                continue
            with self._lock:
                drops = self._pending_source_drops
                self._pending_source_drops = 0
                sequence = self._sequence
                first_index = self._first_sample_index
                self._sequence += 1
                self._first_sample_index += chunk.sample_count + drops
            discontinuity = chunk.discontinuity
            lost_samples = chunk.lost_samples
            if drops:
                discontinuity = Discontinuity.DSP_DROP
                lost_samples = drops
            payload = chunk.payload
            if chunk.payload_format == "CS8":
                # Keep widening work off the time-sensitive UHD read thread.
                # Owned SC8 bytes also consume half the queue bandwidth until
                # immediately before publication to the stable CS16 rings.
                try:
                    values = np.frombuffer(
                        payload, dtype="i1", count=chunk.sample_count * 2
                    ).astype("<i2")
                    np.left_shift(values, 8, out=values)
                    payload = memoryview(values).cast("B")
                finally:
                    if chunk.release is not None:
                        chunk.release(chunk.release_token)
            block = IQBlock(
                source_id=self.source_id,
                epoch=epoch,
                sequence=sequence,
                first_sample_index=first_index,
                sample_count=chunk.sample_count,
                sample_rate_sps=config.sample_rate_sps,
                center_frequency_hz=config.center_frequency_hz,
                config_revision=config.revision,
                sample_format=config.sample_format,
                timestamp_ns=chunk.timestamp_ns,
                time_domain=chunk.time_domain,
                timestamp_origin=chunk.timestamp_origin,
                discontinuity=discontinuity,
                lost_samples=lost_samples,
                payload=payload,
            )
            processing_started = time.perf_counter()
            self.ring.write(block)
            try:
                self._dsp_queue.put_nowait(block)
                depth = self._dsp_queue.qsize()
                with self._lock:
                    self.dsp_queue_high_water = max(self.dsp_queue_high_water, depth)
            except queue.Full:
                # Keep latency bounded: discard the oldest pending DSP block,
                # publish the newest one, and mark the gap on the next block
                # consumed by the DSP worker.
                try:
                    dropped = self._dsp_queue.get_nowait()
                    self._dsp_queue.task_done()
                except queue.Empty:
                    dropped = block
                self._dsp_queue.put_nowait(block)
                now_drop = time.monotonic()
                with self._lock:
                    self.dsp_queue_drops += 1
                    self._pending_dsp_drops += dropped.sample_count
                    total_dsp_drops = self.dsp_queue_drops
                    should_log_dsp_drop = total_dsp_drops == 1 or now_drop >= self._next_dsp_drop_log_at
                    if should_log_dsp_drop:
                        self._next_dsp_drop_log_at = now_drop + 5.0
                if should_log_dsp_drop:
                    logger.warning(
                        "DSP queue is full; oldest pending block was dropped",
                        extra={
                            "code": "DSP_QUEUE_DROP",
                            "run_id": self.run_id,
                            "source_id": self.source_id,
                            "epoch": str(epoch),
                            "details": {
                                "dropped_blocks_total": total_dsp_drops,
                                "queue_capacity_blocks": self.dsp_queue_capacity,
                            },
                        },
                    )
            processing_seconds = time.perf_counter() - processing_started
            block_budget_seconds = block.sample_count / block.sample_rate_sps
            now = time.monotonic()
            with self._lock:
                self.blocks_written += 1
                self.samples_written += block.sample_count
                self._update_rate_measurement_locked(block.sample_count, time.monotonic_ns())
                self.dispatch_processing_seconds += processing_seconds
                self.dispatch_processing_max_ms = max(self.dispatch_processing_max_ms, processing_seconds * 1000.0)
                if processing_seconds > block_budget_seconds:
                    self.dispatch_slow_blocks += 1
                should_log_slow = processing_seconds > block_budget_seconds * 2 and now >= self._next_slow_dispatch_log_at
                if should_log_slow:
                    self._next_slow_dispatch_log_at = now + 5.0
                    queue_depth = self._source_queue.qsize()
            if should_log_slow:
                logger.warning(
                    "dispatcher processing exceeded two block periods",
                    extra={
                        "code": "DISPATCH_SLOW",
                        "run_id": self.run_id,
                        "source_id": self.source_id,
                        "epoch": str(epoch),
                        "details": {
                            "processing_ms": processing_seconds * 1000.0,
                            "block_budget_ms": block_budget_seconds * 1000.0,
                            "queue_depth_blocks": queue_depth,
                        },
                    },
                )
            self._source_queue.task_done()

    @staticmethod
    def _raise_dsp_thread_priority() -> None:
        """Reduce long Windows scheduling pauses without starving the GUI."""
        if os.name != "nt":
            return
        try:
            import ctypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.GetCurrentThread.restype = ctypes.c_void_p
            kernel32.SetThreadPriority.argtypes = (ctypes.c_void_p, ctypes.c_int)
            # Match the Soapy RX thread at THREAD_PRIORITY_ABOVE_NORMAL.  The
            # FFT/SciPy work releases the GIL, so acquisition and DSP can then
            # progress concurrently on separate CPU cores.
            kernel32.SetThreadPriority(kernel32.GetCurrentThread(), 1)
        except Exception:
            logger.debug("could not raise DSP thread priority", exc_info=True)

    def _dsp_loop(self) -> None:
        self._raise_dsp_thread_priority()
        while not self._dsp_stop.is_set() or not self._dsp_queue.empty():
            try:
                block = self._dsp_queue.get(timeout=0.05)
            except queue.Empty:
                continue
            with self._lock:
                drops = self._pending_dsp_drops
                self._pending_dsp_drops = 0
            if drops:
                block = replace(
                    block,
                    discontinuity=Discontinuity.DSP_DROP,
                    lost_samples=drops + int(block.lost_samples or 0),
                )
            started = time.perf_counter()
            failed = None
            try:
                self._pipelines.process(block)
            except Exception as exc:
                failed = exc
            processing_seconds = time.perf_counter() - started
            budget_seconds = block.sample_count / block.sample_rate_sps
            now = time.monotonic()
            with self._lock:
                self.dsp_blocks_processed += 1
                self.dsp_processing_seconds += processing_seconds
                self.dsp_processing_max_ms = max(self.dsp_processing_max_ms, processing_seconds * 1000.0)
                if processing_seconds > budget_seconds:
                    self.dsp_slow_blocks += 1
                if failed is not None:
                    self.dsp_errors += 1
                    self._last_error = str(failed)
                should_log_slow = processing_seconds > budget_seconds * 2 and now >= self._next_slow_dsp_log_at
                if should_log_slow:
                    self._next_slow_dsp_log_at = now + 5.0
                    queue_depth = self._dsp_queue.qsize()
            if failed is not None:
                logger.exception(
                    "DSP pipeline processing failed",
                    exc_info=(type(failed), failed, failed.__traceback__),
                    extra={"code": "DSP_ERROR", "run_id": self.run_id, "source_id": self.source_id, "epoch": str(block.epoch)},
                )
            elif should_log_slow:
                logger.warning(
                    "DSP processing exceeded two block periods",
                    extra={
                        "code": "DSP_SLOW",
                        "run_id": self.run_id,
                        "source_id": self.source_id,
                        "epoch": str(block.epoch),
                        "details": {
                            "processing_ms": processing_seconds * 1000.0,
                            "block_budget_ms": budget_seconds * 1000.0,
                            "queue_depth_blocks": queue_depth,
                        },
                    },
                )
            self._dsp_queue.task_done()

    def apply_config(self, expected_revision: int, requested: RadioConfig | dict) -> RadioConfig:
        with self._command_lock:
            with self._lock:
                if expected_revision != self.config.revision:
                    raise StaleConfigError("STALE_CONFIG")
                current = self.config
                running = self._state is LifecycleState.RUNNING
                # Les réglages de fréquence, gain et options doivent rester
                # transparents pour le flux.  RECONFIGURING est réservé au
                # seul cas où le périphérique doit réellement être arrêté
                # (FS, bande passante ou format de transport IQ).
            if isinstance(requested, dict):
                allowed = {
                    "center_frequency_hz", "sample_rate_sps", "bandwidth_hz",
                    "gain_reduction_db", "agc_enabled", "antenna", "gains", "sample_format",
                    "wire_format",
                }
                unknown = set(requested) - allowed
                if unknown:
                    raise ValueError(f"unknown configuration fields: {sorted(unknown)}")
                candidate = replace(current, **requested, revision=current.revision + 1)
            else:
                candidate = replace(requested, revision=current.revision + 1)
            requires_restart = False
            reopen_source = False
            pipelines_reconfigured = False
            try:
                candidate.validate()
                if candidate.sample_format is not current.sample_format:
                    raise ValueError("source sample format change requires rebuilding the ring")
                requires_restart = running and (
                    candidate.sample_rate_sps != current.sample_rate_sps
                    or candidate.bandwidth_hz != current.bandwidth_hz
                    or candidate.wire_format != current.wire_format
                )
                reopen_source = requires_restart and bool(
                    getattr(self.source, "reopen_on_stream_reconfigure", False)
                )
                if requires_restart:
                    with self._lock:
                        self._state = LifecycleState.RECONFIGURING
                    self.source.stop()
                    self._stop_dispatcher()
                    if reopen_source:
                        if not self.device_id:
                            raise RuntimeError("cannot reopen a source without a device id")
                        self.source.close()
                        self.source.open(self.device_id)
                effective = self.source.configure(candidate)
                with self._lock:
                    self.config = effective
                    self._epoch += 1
                    # La séquence du ring doit rester monotone pour les
                    # lecteurs déjà connectés. La remettre à zéro lors d'un
                    # réglage à chaud faisait ignorer les nouveaux blocs
                    # jusqu'au rattrapage de l'ancienne séquence.
                    self._first_sample_index = 0
                    # Un réglage RF à chaud (fréquence, gain, AGC, antenne,
                    # options RSPdx, voire bande) ne change ni le format ni
                    # le taux d'entrée DSP. Reconstruire ici les filtres de
                    # rééchantillonnage coûtait plusieurs secondes à chaque
                    # mouvement de contrôle. Le pipeline ne doit être
                    # recréé que si le taux ou le format change réellement.
                    if (
                        effective.sample_rate_sps != current.sample_rate_sps
                        or effective.sample_format is not current.sample_format
                    ):
                        self._pipelines.reconfigure(effective.sample_rate_sps, effective.sample_format)
                        pipelines_reconfigured = True
                        self._reset_rate_measurement_locked()
                if requires_restart:
                    self._start_dispatcher()
                    self.source.start(self._on_source_chunk, self._on_source_error)
                with self._lock:
                    self._state = LifecycleState.RUNNING if running else LifecycleState.READY
                    self._last_error = None
                return effective
            except Exception as exc:
                recovered = False
                if running:
                    try:
                        if reopen_source:
                            try:
                                self.source.close()
                            finally:
                                self.source.open(self.device_id)
                        self.source.configure(current)
                        if pipelines_reconfigured:
                            self._pipelines.reconfigure(
                                current.sample_rate_sps, current.sample_format
                            )
                        if requires_restart:
                            self._start_dispatcher()
                            self.source.start(self._on_source_chunk, self._on_source_error)
                        recovered = True
                    except Exception:
                        recovered = False
                with self._lock:
                    self._state = LifecycleState.RUNNING if recovered else LifecycleState.ERROR
                    self._last_error = str(exc)
                raise

    def set_config(self, **changes) -> RadioConfig:
        return self.apply_config(self.config.revision, changes)

    def register_client(self, name: str, profile_id: str | None = None, profile_revision: int = 1) -> tuple[str, RingReader]:
        with self._lock:
            if self.max_clients is not None and len(self._clients) >= self.max_clients:
                raise RuntimeError("configured local client limit reached")
            client_id = uuid.uuid4().hex
            self._clients[client_id] = ClientStats(client_id, str(name)[:128])
            key = None if profile_id is None else (profile_id, int(profile_revision))
            selected_ring = self.ring
            if key is not None:
                shared = self._profile_rings.get(key)
                if shared is None:
                    profile = self.profiles.get(*key)
                    profile.validate(self.config.sample_rate_sps)
                    selected_ring = SharedIQRing(
                        self.ring.slot_count,
                        self.ring.block_samples,
                        sample_format=profile.sample_format,
                        source_id=self.source_id,
                    )
                    token, _ = self._pipelines.subscribe(profile, selected_ring.write)
                    shared = _ProfileRing(selected_ring, token)
                    self._profile_rings[key] = shared
                shared.clients += 1
                selected_ring = shared.ring
            self._client_profile_keys[client_id] = key
            return client_id, RingReader(selected_ring)

    def ring_descriptor_for_client(self, client_id: str) -> dict:
        with self._lock:
            key = self._client_profile_keys[client_id]
            ring = self.ring if key is None else self._profile_rings[key].ring
            return ring.descriptor.to_dict()

    def record_read(self, client_id: str, sequence: int, samples: int, dropped: int) -> None:
        with self._lock:
            stats = self._clients[client_id]
            stats.blocks_read += 1
            stats.samples_read = max(stats.samples_read, int(samples))
            stats.last_sequence = int(sequence)
            stats.dropped_blocks = int(dropped)
            stats.last_seen_ns = time.monotonic_ns()

    def unregister_client(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)
            key = self._client_profile_keys.pop(client_id, None)
            if key is not None and key in self._profile_rings:
                shared = self._profile_rings[key]
                shared.clients -= 1
                if shared.clients == 0:
                    self._pipelines.unsubscribe(shared.pipeline_token)
                    shared.ring.close(unlink=True)
                    del self._profile_rings[key]

    def subscribe_profile(self, profile_id: str, revision: int, callback: Callable[[IQBlock], None]) -> tuple[str, object]:
        profile = self.profiles.get(profile_id, revision)
        return self._pipelines.subscribe(profile, callback)

    def subscribe_stream_profile(self, profile: StreamProfile, callback: Callable[[IQBlock], None]) -> tuple[str, object]:
        """Subscribe an operator-owned immutable profile without publishing it globally."""
        return self._pipelines.subscribe(profile, callback)

    def unsubscribe_profile(self, token: str) -> bool:
        return self._pipelines.unsubscribe(token)

    def status(self) -> dict:
        with self._lock:
            measured_rate = self._sample_rate_measured
            if self._rate_last_write_ns and time.monotonic_ns() - self._rate_last_write_ns > 1_000_000_000:
                measured_rate = 0.0
            pipeline_snapshot = self._pipelines.snapshot()
            source_diagnostics = getattr(self.source, "diagnostics", None)
            return {
                "run_id": getattr(self, "run_id", None),
                "state": self._state.value,
                "running": self._state is LifecycleState.RUNNING,
                "source": self.source.name,
                "source_id": self.source_id,
                "device_id": self.device_id,
                "epoch": str(self._epoch),
                "config": self.config.to_dict(),
                "ring": self.ring.descriptor.to_dict(),
                "blocks_received": self.blocks_received,
                "samples_received": self.samples_received,
                "blocks_written": self.blocks_written,
                "samples_written": self.samples_written,
                "source_queue_drops": self.source_queue_drops,
                "source_queue_capacity": self.source_queue_capacity,
                "source_queue_high_water": self.source_queue_high_water,
                "source_losses": self.source_losses,
                "source_errors": self.source_errors,
                "source_diagnostics": source_diagnostics() if callable(source_diagnostics) else {},
                "dispatch_processing_average_ms": self.dispatch_processing_seconds * 1000.0 / self.blocks_written if self.blocks_written else 0.0,
                "dispatch_processing_max_ms": self.dispatch_processing_max_ms,
                "dispatch_slow_blocks": self.dispatch_slow_blocks,
                "dsp_queue_drops": self.dsp_queue_drops,
                "dsp_queue_capacity": self.dsp_queue_capacity,
                "dsp_queue_high_water": self.dsp_queue_high_water,
                "dsp_blocks_processed": self.dsp_blocks_processed,
                "dsp_processing_average_ms": self.dsp_processing_seconds * 1000.0 / self.dsp_blocks_processed if self.dsp_blocks_processed else 0.0,
                "dsp_processing_max_ms": self.dsp_processing_max_ms,
                "dsp_slow_blocks": self.dsp_slow_blocks,
                "dsp_errors": self.dsp_errors,
                "profile_queue_drops": sum(
                    int(item.get("parallel_queue_drops", 0)) for item in pipeline_snapshot
                ),
                "last_error": self._last_error,
                "sample_rate_measured": measured_rate if self._state is LifecycleState.RUNNING else 0.0,
                "clients": [item.to_dict() for item in self._clients.values()],
                "pipelines": pipeline_snapshot,
            }
