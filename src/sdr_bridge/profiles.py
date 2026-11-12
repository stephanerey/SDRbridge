from __future__ import annotations

from dataclasses import dataclass, field, replace
import logging
import queue
import threading
import uuid
from typing import Callable

from .dsp import DSPPipeline
from .model import Discontinuity, IQBlock, SampleFormat, StreamProfile


logger = logging.getLogger(__name__)


DEFAULT_PROFILES = (
    StreamProfile("master-cs16", 1, 2_000_000, SampleFormat.CS16, "ring_v2", name="Master CS16"),
    StreamProfile("antrack-192k", 1, 192_000, SampleFormat.CS16, "ring_v2", name="ANTRACK 192 kS/s"),
    StreamProfile("antrack-96k", 1, 96_000, SampleFormat.CS16, "ring_v2", name="ANTRACK 96 kS/s"),
    StreamProfile("native-cf32-192k", 1, 192_000, SampleFormat.CF32, "sdbu_v2", name="Natif CF32 192 kS/s"),
    StreamProfile("native-cs16-192k", 1, 192_000, SampleFormat.CS16, "sdbu_v2", name="Natif CS16 192 kS/s"),
    StreamProfile("sdrpp-raw-192k", 1, 192_000, SampleFormat.CS16, "sdrpp_raw_cs16", name="SDR++ raw 192 kS/s"),
    StreamProfile("qmap-linrad-96k", 1, 96_000, SampleFormat.CS16, "qmap_linrad", name="QMAP / Linrad 96 kS/s"),
)


class ProfileRegistry:
    def __init__(self, profiles=DEFAULT_PROFILES):
        self._profiles: dict[tuple[str, int], StreamProfile] = {}
        for profile in profiles:
            self.add(profile)

    def add(self, profile: StreamProfile) -> None:
        profile.validate()
        key = (profile.profile_id, profile.profile_revision)
        if key in self._profiles:
            raise ValueError("profile revision already exists")
        self._profiles[key] = profile

    def get(self, profile_id: str, revision: int) -> StreamProfile:
        try:
            return self._profiles[(profile_id, int(revision))]
        except KeyError as exc:
            raise KeyError("UNKNOWN_PROFILE") from exc

    def items(self) -> list[StreamProfile]:
        return list(self._profiles.values())


@dataclass(slots=True)
class _SharedPipeline:
    processor: DSPPipeline
    consumers: dict[str, Callable[[IQBlock], None]] = field(default_factory=dict)
    profile: StreamProfile | None = None
    parent_key: tuple | None = None
    consumer_lock: threading.RLock = field(default_factory=threading.RLock)


@dataclass(slots=True)
class _PipelineWorker:
    key: tuple
    shared: _SharedPipeline
    queue: queue.Queue[IQBlock]
    stop: threading.Event
    thread: threading.Thread | None
    queue_drops: int = 0
    pending_lost_samples: int = 0
    state_lock: threading.Lock = field(default_factory=threading.Lock)


class PipelinePool:
    _PARALLEL_RATE_THRESHOLD = 8_000_000

    def __init__(
        self,
        source_id: str,
        input_rate: int,
        input_format: SampleFormat,
        *,
        parallel_workers: int = 1,
    ):
        if parallel_workers <= 0:
            raise ValueError("parallel_workers must be positive")
        self.source_id = source_id
        self.input_rate = input_rate
        self.input_format = input_format
        self.parallel_workers = int(parallel_workers)
        self._lock = threading.RLock()
        self._pipelines: dict[tuple, _SharedPipeline] = {}
        self._workers: dict[tuple, _PipelineWorker] = {}
        # A child profile consumes the output of its parent asynchronously.
        # Windows can occasionally suspend Python workers for a few hundred
        # milliseconds even when the average DSP time is comfortably below
        # the block budget.  At 16 MS/s, 64 input-duration blocks only cover
        # about 131 ms; 256 cover about 524 ms while using only a few MiB for
        # the usual 2 MS/s -> 96 kS/s child stage.
        self._parallel_queue_blocks = 256

    def _key(self, profile: StreamProfile) -> tuple:
        return (self.source_id, self.input_rate, self.input_format, profile.output_rate_sps, profile.sample_format, profile.center_offset_hz)

    @staticmethod
    def _profile_rate(shared: _SharedPipeline) -> int:
        return int(shared.profile.output_rate_sps) if shared.profile is not None else shared.processor.output_rate

    def _select_parent_key(self, profile: StreamProfile, pipelines: dict[tuple, _SharedPipeline] | None = None) -> tuple | None:
        available = self._pipelines if pipelines is None else pipelines
        candidates = [
            (key, shared)
            for key, shared in available.items()
            if shared.profile is not None
            and shared.profile.center_offset_hz == profile.center_offset_hz
            and shared.profile.output_rate_sps > profile.output_rate_sps
        ]
        if not candidates:
            return None
        # The nearest higher-rate result minimizes the work left to the child.
        # Prefer the same sample format when rates are equal to avoid a format
        # conversion between stages.
        return min(
            candidates,
            key=lambda item: (
                self._profile_rate(item[1]),
                item[1].processor.output_format is not profile.sample_format,
            ),
        )[0]

    def _make_shared(
        self,
        profile: StreamProfile,
        consumers: dict[str, Callable[[IQBlock], None]],
        pipelines: dict[tuple, _SharedPipeline],
        metrics: tuple[int, int, int, int] = (0, 0, 0, 0),
    ) -> _SharedPipeline:
        parent_key = self._select_parent_key(profile, pipelines)
        if parent_key is None:
            input_rate = self.input_rate
            input_format = self.input_format
        else:
            parent = pipelines[parent_key].processor
            input_rate = parent.output_rate
            input_format = parent.output_format
        processor = DSPPipeline(
            self.source_id,
            input_rate,
            input_format,
            profile.output_rate_sps,
            profile.sample_format,
        )
        processor.sequence, processor.blocks_processed, processor.samples_produced, processor.errors = metrics
        return _SharedPipeline(processor, consumers, profile, parent_key)

    @staticmethod
    def _pipeline_root_key(key: tuple, pipelines: dict[tuple, _SharedPipeline]) -> tuple:
        current = key
        visited: set[tuple] = set()
        while current in pipelines and current not in visited:
            visited.add(current)
            parent_key = pipelines[current].parent_key
            if parent_key is None or parent_key not in pipelines:
                return current
            current = parent_key
        return key

    @staticmethod
    def _enqueue_worker(worker: _PipelineWorker, block: IQBlock) -> None:
        try:
            worker.queue.put_nowait(block)
            return
        except queue.Full:
            pass
        try:
            dropped = worker.queue.get_nowait()
            worker.queue.task_done()
        except queue.Empty:
            dropped = block
        with worker.state_lock:
            worker.queue_drops += 1
            worker.pending_lost_samples += dropped.sample_count
        try:
            worker.queue.put_nowait(block)
        except queue.Full:
            # A concurrent producer won the freed slot. Account for the new
            # block too instead of ever blocking an upstream DSP stage.
            with worker.state_lock:
                worker.queue_drops += 1
                worker.pending_lost_samples += block.sample_count

    def _worker_loop(self, worker: _PipelineWorker) -> None:
        while not worker.stop.is_set():
            try:
                block = worker.queue.get(timeout=0.05)
            except queue.Empty:
                continue
            try:
                with worker.state_lock:
                    lost_samples = worker.pending_lost_samples
                    worker.pending_lost_samples = 0
                if lost_samples:
                    block = replace(
                        block,
                        discontinuity=Discontinuity.DSP_DROP,
                        lost_samples=int(block.lost_samples or 0) + lost_samples,
                    )
                output = worker.shared.processor.process(block)
                if output is not None:
                    with worker.shared.consumer_lock:
                        callbacks = list(worker.shared.consumers.values())
                        for callback in callbacks:
                            callback(output)
                    # Pipeline children run on their own workers. This retains
                    # the arithmetic saving of a cascade while letting Windows
                    # schedule adjacent resampling stages on different cores.
                    pipelines = dict(self._pipelines)
                    workers = dict(self._workers)
                    for child_key, child in pipelines.items():
                        if child.parent_key == worker.key and child_key in workers:
                            self._enqueue_worker(workers[child_key], output)
            except Exception:
                logger.exception(
                    "parallel DSP profile processing failed",
                    extra={
                        "code": "PROFILE_DSP_ERROR",
                        "source_id": block.source_id,
                        "epoch": str(block.epoch),
                        "details": {"output_rate_sps": worker.shared.processor.output_rate},
                    },
                )
            finally:
                worker.queue.task_done()

    def _ensure_worker_locked(self, key: tuple, shared: _SharedPipeline) -> _PipelineWorker:
        worker = self._workers.get(key)
        if worker is not None:
            return worker
        pending: queue.Queue[IQBlock] = queue.Queue(maxsize=self._parallel_queue_blocks)
        stop = threading.Event()
        placeholder = _PipelineWorker(key, shared, pending, stop, None)
        thread = threading.Thread(
            target=self._worker_loop,
            args=(placeholder,),
            name=f"sdrbridge-dsp-{shared.processor.output_rate}",
            daemon=True,
        )
        placeholder.thread = thread
        self._workers[key] = placeholder
        thread.start()
        return placeholder

    @staticmethod
    def _stop_worker(worker: _PipelineWorker) -> None:
        worker.stop.set()
        if worker.thread is not None and worker.thread is not threading.current_thread():
            worker.thread.join(timeout=2.0)
            if worker.thread.is_alive():
                raise RuntimeError("parallel DSP profile worker did not stop")
        while True:
            try:
                worker.queue.get_nowait()
                worker.queue.task_done()
            except queue.Empty:
                break

    def _stop_all_workers_locked(self) -> None:
        workers = list(self._workers.values())
        self._workers.clear()
        for worker in workers:
            self._stop_worker(worker)

    def _rebuild_locked(self, existing: list[tuple[StreamProfile, dict[str, Callable[[IQBlock], None]], tuple[int, int, int, int]]]) -> None:
        self._stop_all_workers_locked()
        rebuilt: dict[tuple, _SharedPipeline] = {}
        for profile, consumers, metrics in sorted(existing, key=lambda item: item[0].output_rate_sps, reverse=True):
            key = self._key(profile)
            rebuilt[key] = self._make_shared(profile, consumers, rebuilt, metrics)
        self._pipelines = rebuilt

    def subscribe(self, profile: StreamProfile, callback: Callable[[IQBlock], None]) -> tuple[str, DSPPipeline]:
        profile.validate(self.input_rate)
        key = self._key(profile)
        with self._lock:
            shared = self._pipelines.get(key)
            if shared is None:
                shared = self._make_shared(profile, {}, self._pipelines)
                self._pipelines[key] = shared
            token = uuid.uuid4().hex
            with shared.consumer_lock:
                shared.consumers[token] = callback
            return token, shared.processor

    def unsubscribe(self, token: str) -> bool:
        with self._lock:
            for key, shared in list(self._pipelines.items()):
                if token in shared.consumers:
                    with shared.consumer_lock:
                        del shared.consumers[token]
                    if not shared.consumers:
                        worker = self._workers.pop(key, None)
                        if worker is not None:
                            self._stop_worker(worker)
                        del self._pipelines[key]
                        if any(item.parent_key == key for item in self._pipelines.values()):
                            existing = [
                                (
                                    item.profile,
                                    dict(item.consumers),
                                    (
                                        item.processor.sequence,
                                        item.processor.blocks_processed,
                                        item.processor.samples_produced,
                                        item.processor.errors,
                                    ),
                                )
                                for item in self._pipelines.values()
                                if item.profile is not None
                            ]
                            self._rebuild_locked(existing)
                    return True
        return False

    def process(self, block: IQBlock) -> None:
        with self._lock:
            pipelines = sorted(
                self._pipelines.items(),
                key=lambda item: self._profile_rate(item[1]),
                reverse=True,
            )
            if self.parallel_workers > 1 and self.input_rate >= self._PARALLEL_RATE_THRESHOLD:
                # Process roots in the bridge DSP worker itself. Feeding the
                # first decimator through another 64-block Python queue added
                # scheduling jitter and could overflow at 16 MS/s even though
                # the filter had enough sustained throughput. The bridge DSP
                # queue already provides 256 blocks of bounded back-pressure.
                # Children retain their own workers, so adjacent cascade stages
                # still execute on separate CPU cores.
                for key, shared in pipelines:
                    if shared.parent_key is not None:
                        self._ensure_worker_locked(key, shared)
                pipeline_map = dict(self._pipelines)
                workers = dict(self._workers)
                for key, shared in pipelines:
                    if shared.parent_key is not None:
                        continue
                    output = shared.processor.process(block)
                    if output is None:
                        continue
                    with shared.consumer_lock:
                        callbacks = list(shared.consumers.values())
                    for callback in callbacks:
                        callback(output)
                    for child_key, child in pipeline_map.items():
                        if child.parent_key == key and child_key in workers:
                            self._enqueue_worker(workers[child_key], output)
                return
            produced: dict[tuple, IQBlock] = {}
            # Garder le verrou pendant l'émission protège les rings de profil
            # contre un unsubscribe concurrent qui les fermerait alors qu'un
            # callback est encore en train d'écrire.
            for key, shared in pipelines:
                input_block = block if shared.parent_key is None else produced.get(shared.parent_key)
                if input_block is None:
                    continue
                output = shared.processor.process(input_block)
                if output is None:
                    continue
                produced[key] = output
                with shared.consumer_lock:
                    callbacks = list(shared.consumers.values())
                for callback in callbacks:
                    callback(output)

    def close(self) -> None:
        with self._lock:
            self._stop_all_workers_locked()

    @property
    def pipeline_count(self) -> int:
        with self._lock:
            return len(self._pipelines)

    def reconfigure(self, input_rate: int, input_format: SampleFormat) -> None:
        with self._lock:
            existing = [
                (
                    shared.profile,
                    dict(shared.consumers),
                    (
                        shared.processor.sequence,
                        shared.processor.blocks_processed,
                        shared.processor.samples_produced,
                        shared.processor.errors,
                    ),
                )
                for shared in self._pipelines.values()
                if shared.profile is not None
            ]
            # Validate every active profile before mutating the pool. A file
            # with a narrower rate must not leave half of the destinations
            # rebuilt if one profile cannot be served.
            for profile, _consumers, _metrics in existing:
                profile.validate(int(input_rate))
            self.input_rate = int(input_rate)
            self.input_format = input_format
            # The profile rings and their readers survive this rebuild. New
            # filters are correct for the new source epoch, while publication
            # sequence counters stay monotone for existing readers.
            self._rebuild_locked(existing)

    def snapshot(self) -> list[dict]:
        with self._lock:
            roots = {
                key: self._pipeline_root_key(key, self._pipelines)
                for key in self._pipelines
            }
            return [
                {
                    "output_rate_sps": shared.processor.output_rate,
                    "input_rate_sps": shared.processor.input_rate,
                    "output_format": shared.processor.output_format.value,
                    "shared_parent_rate_sps": (
                        self._pipelines[shared.parent_key].processor.output_rate
                        if shared.parent_key is not None and shared.parent_key in self._pipelines
                        else None
                    ),
                    "subscribers": len(shared.consumers),
                    "blocks_processed": shared.processor.blocks_processed,
                    "samples_produced": shared.processor.samples_produced,
                    "group_delay_seconds": shared.processor.group_delay_seconds,
                    "errors": shared.processor.errors,
                    "parallel_workers": len(self._workers),
                    "parallel_root_rate_sps": (
                        self._pipelines[roots[key]].processor.output_rate
                        if roots[key] in self._pipelines
                        else None
                    ),
                    "parallel_queue_drops": (
                        self._workers[key].queue_drops if key in self._workers else 0
                    ),
                    "parallel_queue_depth": (
                        self._workers[key].queue.qsize() if key in self._workers else 0
                    ),
                }
                for key, shared in self._pipelines.items()
            ]
