from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import tempfile
import threading
import time
from typing import BinaryIO, Callable

import jsonschema

from .config import schema_path
from .model import (
    DeviceCapabilities,
    DeviceDescriptor,
    Discontinuity,
    IQBlock,
    RadioConfig,
    SampleFormat,
    TimeDomain,
    TimestampOrigin,
)
from .source import BlockCallback, ErrorCallback, IQSource, SourceChunk

SIGMF_VERSION = "1.2.6"


def _paths(base: str | Path) -> tuple[Path, Path]:
    path = Path(base)
    if path.suffix == ".sigmf-meta":
        path = path.with_suffix("")
    elif path.suffix == ".sigmf-data":
        path = path.with_suffix("")
    return Path(str(path) + ".sigmf-data"), Path(str(path) + ".sigmf-meta")


def validate_sigmf(meta: dict, data_path: Path) -> int:
    schema = json.loads(schema_path("sigmf-1.2.6.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(meta)
    global_meta = meta["global"]
    if global_meta.get("core:version") != SIGMF_VERSION:
        raise ValueError("unsupported SigMF version")
    datatype = global_meta.get("core:datatype")
    if datatype not in {SampleFormat.CS16.value, SampleFormat.CF32.value}:
        raise ValueError("unsupported SigMF datatype")
    if global_meta.get("core:num_channels", 1) != 1:
        raise ValueError("only monophonic SigMF is supported")
    if "core:dataset" in global_meta or "core:header_bytes" in global_meta or "core:trailing_bytes" in global_meta:
        raise ValueError("non-conforming SigMF datasets are unsupported")
    if not isinstance(global_meta.get("core:sample_rate"), int) or global_meta["core:sample_rate"] <= 0:
        raise ValueError("SigMF sample rate must be a positive integer")
    captures = meta.get("captures")
    if not isinstance(captures, list) or len(captures) != 1 or captures[0].get("core:sample_start") != 0:
        raise ValueError("V1 replay requires exactly one capture at sample_start zero")
    if "core:frequency" not in captures[0]:
        raise ValueError("SigMF center frequency is required")
    bytes_per_iq = SampleFormat(datatype).bytes_per_iq
    size = data_path.stat().st_size
    if size % bytes_per_iq:
        raise ValueError("SigMF data ends with a partial IQ sample")
    return size // bytes_per_iq


class SigMFRecorder:
    def __init__(
        self,
        base_path: str | Path,
        sample_rate_sps: int,
        sample_format: SampleFormat,
        center_frequency_hz: int,
        *,
        queue_blocks: int = 64,
        writer_factory: Callable[[Path], BinaryIO] | None = None,
    ):
        self.data_path, self.meta_path = _paths(base_path)
        if self.data_path.exists() or self.meta_path.exists():
            raise FileExistsError("SigMF output already exists")
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self.sample_rate_sps = int(sample_rate_sps)
        self.sample_format = sample_format
        self.center_frequency_hz = int(center_frequency_hz)
        self._writer_factory = writer_factory or (lambda path: path.open("xb"))
        self._queue: queue.Queue[IQBlock] = queue.Queue(maxsize=queue_blocks)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._stream: BinaryIO | None = None
        self._epoch: int | None = None
        self._started_blocks = 0
        self.bytes_written = 0
        self.samples_written = 0
        self.incomplete = False
        self.reason: str | None = None
        self.finalized = False

    def start(self) -> None:
        self._stream = self._writer_factory(self.data_path)
        self._thread = threading.Thread(target=self._run, name="sigmf-recorder", daemon=True)
        self._thread.start()

    def enqueue(self, block: IQBlock) -> None:
        if self._stop.is_set():
            return
        if block.sample_format is not self.sample_format or block.sample_rate_sps != self.sample_rate_sps:
            self._fail("changement de taux ou format")
            return
        if self._epoch is None:
            self._epoch = block.epoch
        elif block.epoch != self._epoch or block.discontinuity is not Discontinuity.NONE:
            self._fail("discontinuité du flux")
            return
        try:
            self._queue.put_nowait(block)
        except queue.Full:
            self._fail("file recorder saturée")

    def _fail(self, reason: str) -> None:
        self.incomplete = True
        self.reason = reason
        self._stop.set()

    def stop(self, reason: str | None = None) -> None:
        if reason and self.reason is None:
            self.reason = reason
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                raise RuntimeError("recorder did not stop")

    def _run(self) -> None:
        try:
            while not self._stop.is_set() or not self._queue.empty():
                try:
                    block = self._queue.get(timeout=.05)
                except queue.Empty:
                    continue
                try:
                    raw = bytes(block.payload)
                    written = self._stream.write(raw)
                    if written is not None and written != len(raw):
                        raise OSError("short recorder write")
                    self.bytes_written += len(raw)
                    self.samples_written += block.sample_count
                    self._started_blocks += 1
                except OSError as exc:
                    self._fail(f"écriture impossible: {exc}")
                finally:
                    self._queue.task_done()
        finally:
            if self._stream:
                try:
                    self._stream.flush()
                    os.fsync(self._stream.fileno())
                except (OSError, AttributeError):
                    self.incomplete = True
                self._stream.close()
            self._finalize_metadata()

    def _finalize_metadata(self) -> None:
        description = "Capture SDRbridge"
        if self.reason:
            description += f" — arrêt: {self.reason}"
        if self.incomplete:
            description += " — incomplète"
        meta = {
            "global": {
                "core:version": SIGMF_VERSION,
                "core:datatype": self.sample_format.value,
                "core:sample_rate": self.sample_rate_sps,
                "core:num_channels": 1,
                "core:recorder": "SDRbridge",
                "core:description": description,
            },
            "captures": [{"core:sample_start": 0, "core:frequency": self.center_frequency_hz}],
            "annotations": [],
        }
        jsonschema.Draft202012Validator(json.loads(schema_path("sigmf-1.2.6.schema.json").read_text(encoding="utf-8"))).validate(meta)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{self.meta_path.name}.", suffix=".tmp", dir=self.meta_path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(meta, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, self.meta_path)
            self.finalized = True
        except BaseException:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise


class ReplaySource(IQSource):
    DEVICE_PREFIX = "replay:"

    def __init__(self, path: str | Path, block_samples: int = 4096, *, realtime: bool = True):
        self.data_path, self.meta_path = _paths(path)
        self.block_samples = int(block_samples)
        self.realtime = realtime
        self._meta: dict | None = None
        self._sample_count = 0
        self._position = 0
        self._config: RadioConfig | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._on_block: BlockCallback | None = None
        self._on_error: ErrorCallback | None = None
        self._seek_pending = False
        self.eof = False

    @property
    def name(self) -> str:
        return f"Replay SigMF — {self.meta_path.name}"

    @property
    def device_id(self) -> str:
        return self.DEVICE_PREFIX + str(self.meta_path.resolve())

    def enumerate(self) -> list[DeviceDescriptor]:
        return [DeviceDescriptor(self.device_id, "replay", self.name, serial=None)] if self.meta_path.exists() and self.data_path.exists() else []

    def open(self, device_id: str | None = None) -> None:
        if device_id is not None and device_id != self.device_id:
            raise KeyError(device_id)
        self._meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
        self._sample_count = validate_sigmf(self._meta, self.data_path)
        global_meta = self._meta["global"]
        capture = self._meta["captures"][0]
        sample_format = SampleFormat(global_meta["core:datatype"])
        rate = int(global_meta["core:sample_rate"])
        frequency = int(capture["core:frequency"])
        self._config = RadioConfig(frequency, rate, min(rate, rate), 0, False, sample_format=sample_format)
        self._position = 0
        self.eof = False

    def capabilities(self, device_id: str) -> DeviceCapabilities:
        if self._config is None:
            self.open(device_id)
        return DeviceCapabilities(device_id, ((self._config.center_frequency_hz, self._config.center_frequency_hz + 1),), (self._config.sample_rate_sps,), (self._config.bandwidth_hz,), (), {}, False, (self._config.sample_format,))

    def configure(self, request: RadioConfig) -> RadioConfig:
        if self._config is None:
            raise RuntimeError("replay is not open")
        self._config = RadioConfig(
            self._config.center_frequency_hz, self._config.sample_rate_sps, self._config.bandwidth_hz,
            self._config.gain_reduction_db, self._config.agc_enabled, sample_format=self._config.sample_format,
            revision=request.revision,
        )
        return self._config

    def start(self, on_block: BlockCallback, on_error: ErrorCallback | None = None) -> None:
        if self._config is None:
            raise RuntimeError("replay is not open")
        if self._thread and self._thread.is_alive():
            raise RuntimeError("replay already started")
        self._on_block, self._on_error = on_block, on_error
        self._stop.clear(); self.eof = False
        self._thread = threading.Thread(target=self._run, name="sigmf-replay", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)
        self._thread = None

    def close(self) -> None:
        self.stop()
        self._meta = None
        self._config = None

    def seek(self, sample_index: int) -> None:
        if not 0 <= sample_index <= self._sample_count:
            raise ValueError("replay seek out of range")
        self._position = int(sample_index)
        self._seek_pending = True
        self.eof = False

    def _run(self) -> None:
        try:
            bytes_per_iq = self._config.sample_format.bytes_per_iq
            next_deadline = time.perf_counter()
            with self.data_path.open("rb") as stream:
                while not self._stop.is_set() and self._position < self._sample_count:
                    position = self._position
                    stream.seek(position * bytes_per_iq)
                    count = min(self.block_samples, self._sample_count - position)
                    raw = stream.read(count * bytes_per_iq)
                    if len(raw) != count * bytes_per_iq:
                        raise OSError("truncated SigMF data during replay")
                    discontinuity = Discontinuity.REPLAY_SEEK if self._seek_pending else (Discontinuity.START if position == 0 else Discontinuity.NONE)
                    self._seek_pending = False
                    self._on_block(SourceChunk(
                        memoryview(raw), count, position,
                        round(position * 1_000_000_000 / self._config.sample_rate_sps),
                        TimeDomain.REPLAY_RELATIVE, TimestampOrigin.DERIVED, discontinuity, 0,
                    ))
                    self._position += count
                    if self.realtime:
                        next_deadline += count / self._config.sample_rate_sps
                        self._stop.wait(max(0.0, next_deadline - time.perf_counter()))
            if self._position >= self._sample_count:
                self.eof = True
        except BaseException as exc:
            if self._on_error and not self._stop.is_set():
                self._on_error(exc)
