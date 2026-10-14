from __future__ import annotations

from dataclasses import replace
import queue
import threading
import time
import uuid
from typing import Callable
from dataclasses import dataclass

from .model import (
    ClientStats,
    Discontinuity,
    IQBlock,
    LifecycleState,
    RadioConfig,
)
from .profiles import PipelinePool, ProfileRegistry
from .dsp import design_resampler_filter
from .ring import RingReader, SharedIQRing
from .source import IQSource, SourceChunk


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
        max_clients: int | None = None,
        source_id: str = "source-0",
        device_id: str | None = None,
    ):
        self.source = source
        self.config = config or RadioConfig()
        self.config.validate()
        if max_clients is not None and max_clients <= 0:
            raise ValueError("max_clients must be null or positive")
        if source_queue_blocks <= 0:
            raise ValueError("source_queue_blocks must be positive")
        self.max_clients = max_clients
        self.source_id = source_id
        self.device_id = device_id
        self.ring = SharedIQRing(slots, block_samples, sample_format=self.config.sample_format, source_id=source_id)
        self.profiles = ProfileRegistry()
        for output_rate in (192_000, 96_000):
            if output_rate < self.config.sample_rate_sps:
                design_resampler_filter(self.config.sample_rate_sps, output_rate)
        self._pipelines = PipelinePool(source_id, self.config.sample_rate_sps, self.config.sample_format)
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
        self.source_queue_capacity = int(source_queue_blocks)
        self.source_queue_high_water = 0
        self._dispatch_stop = threading.Event()
        self._dispatch_thread: threading.Thread | None = None
        self._recovery_cancel = threading.Event()
        self._pending_source_drops = 0
        self._closed = False
        self.started_ns = 0
        self.blocks_received = 0
        self.samples_received = 0
        self.blocks_written = 0
        self.samples_written = 0
        self.source_queue_drops = 0
        self.source_errors = 0

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
            effective = self.source.configure(self.config)
            with self._lock:
                self.device_id = device_id
                self.config = effective
                self._epoch += 1
                self._sequence = 0
                self._first_sample_index = 0
            if running:
                self.start()

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
                self._sequence = 0
                self._first_sample_index = 0
                self.started_ns = time.monotonic_ns()
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

    def _clear_source_queue(self) -> None:
        while True:
            try:
                self._source_queue.get_nowait()
                self._source_queue.task_done()
            except queue.Empty:
                return

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
                        self._sequence = 0
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
                self.ring.close(unlink=True)
                self._closed = True
                with self._lock:
                    self._state = LifecycleState.IDLE

    def _on_source_chunk(self, chunk: SourceChunk) -> None:
        # Le callback ne fait qu'une copie possédée et un enqueue borné.
        owned = SourceChunk(
            payload=memoryview(bytes(chunk.payload)),
            sample_count=chunk.sample_count,
            first_sample_index=chunk.first_sample_index,
            timestamp_ns=chunk.timestamp_ns,
            time_domain=chunk.time_domain,
            timestamp_origin=chunk.timestamp_origin,
            discontinuity=chunk.discontinuity,
            lost_samples=chunk.lost_samples,
        )
        with self._lock:
            if chunk.discontinuity is Discontinuity.REPLAY_SEEK or (
                chunk.discontinuity is Discontinuity.SOURCE_LOSS and chunk.lost_samples is None
            ):
                self._epoch += 1
                self._sequence = 0
                self._first_sample_index = 0
            config, epoch = self.config, self._epoch
            self.blocks_received += 1
            self.samples_received += chunk.sample_count
        try:
            self._source_queue.put_nowait((owned, config, epoch))
            depth = self._source_queue.qsize()
            with self._lock:
                self.source_queue_high_water = max(self.source_queue_high_water, depth)
        except queue.Full:
            with self._lock:
                self.source_queue_drops += 1
                self._pending_source_drops += chunk.sample_count

    def _on_source_error(self, exc: BaseException) -> None:
        with self._lock:
            self.source_errors += 1
            self._last_error = str(exc)
            self._state = LifecycleState.ERROR

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
                payload=chunk.payload,
            )
            self.ring.write(block)
            self._pipelines.process(block)
            with self._lock:
                self.blocks_written += 1
                self.samples_written += block.sample_count
            self._source_queue.task_done()

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
                # (FS ou bande passante).
            if isinstance(requested, dict):
                allowed = {
                    "center_frequency_hz", "sample_rate_sps", "bandwidth_hz",
                    "gain_reduction_db", "agc_enabled", "antenna", "gains", "sample_format",
                }
                unknown = set(requested) - allowed
                if unknown:
                    raise ValueError(f"unknown configuration fields: {sorted(unknown)}")
                candidate = replace(current, **requested, revision=current.revision + 1)
            else:
                candidate = replace(requested, revision=current.revision + 1)
            requires_restart = False
            try:
                candidate.validate()
                if candidate.sample_format is not current.sample_format:
                    raise ValueError("source sample format change requires rebuilding the ring")
                requires_restart = running and (
                    candidate.sample_rate_sps != current.sample_rate_sps
                    or candidate.bandwidth_hz != current.bandwidth_hz
                )
                if requires_restart:
                    with self._lock:
                        self._state = LifecycleState.RECONFIGURING
                    self.source.stop()
                    self._stop_dispatcher()
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
                        self.source.configure(current)
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

    def unsubscribe_profile(self, token: str) -> bool:
        return self._pipelines.unsubscribe(token)

    def status(self) -> dict:
        with self._lock:
            elapsed = max(1, time.monotonic_ns() - self.started_ns) if self.started_ns else 1
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
                "source_errors": self.source_errors,
                "last_error": self._last_error,
                "sample_rate_measured": self.samples_written * 1e9 / elapsed if self.running else 0.0,
                "clients": [item.to_dict() for item in self._clients.values()],
                "pipelines": self._pipelines.snapshot(),
            }
