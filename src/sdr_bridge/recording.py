from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import json
import os
from pathlib import Path
import queue
import re
import struct
import tempfile
import threading
import time
from typing import BinaryIO, Callable

import jsonschema
import numpy as np

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


class CaptureFormat(str, Enum):
    SIGMF = "sigmf"
    SDRPP_WAV = "sdrpp_wav"
    HDSDR_WAV = "hdsdr_wav"


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
        self.output_path = self.meta_path
        self.capture_format = CaptureFormat.SIGMF
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


_SDRPP_FREQUENCY_RE = re.compile(r"(?<!\d)\d+Hz(?![A-Za-z])", re.IGNORECASE)


def _wav_output_path(path: str | Path, capture_format: CaptureFormat, center_frequency_hz: int) -> Path:
    output = Path(path)
    if output.suffix.lower() != ".wav":
        output = output.with_suffix(".wav")
    if capture_format is CaptureFormat.SDRPP_WAV and not _SDRPP_FREQUENCY_RE.search(output.stem):
        output = output.with_name(f"{output.stem}_{int(center_frequency_hz)}Hz.wav")
    return output


def _system_time(value: datetime) -> bytes:
    value = value.astimezone(timezone.utc)
    # Windows SYSTEMTIME uses Sunday=0 whereas datetime.weekday uses Monday=0.
    day_of_week = (value.weekday() + 1) % 7
    return struct.pack(
        "<8H",
        value.year,
        value.month,
        day_of_week,
        value.day,
        value.hour,
        value.minute,
        value.second,
        value.microsecond // 1000,
    )


class WAVRecorder:
    """Queued stereo IQ recorder compatible with SDR++ or HDSDR."""

    def __init__(
        self,
        output_path: str | Path,
        sample_rate_sps: int,
        sample_format: SampleFormat,
        center_frequency_hz: int,
        *,
        capture_format: CaptureFormat,
        queue_blocks: int = 64,
    ):
        if capture_format not in {CaptureFormat.SDRPP_WAV, CaptureFormat.HDSDR_WAV}:
            raise ValueError("WAVRecorder requires an SDR++ or HDSDR capture format")
        self.capture_format = capture_format
        self.sample_rate_sps = int(sample_rate_sps)
        self.sample_format = sample_format
        self.center_frequency_hz = int(center_frequency_hz)
        if not 0 < self.sample_rate_sps <= 0xFFFFFFFF:
            raise ValueError("WAV sample rate must fit in uint32")
        if capture_format is CaptureFormat.HDSDR_WAV and not 0 < self.center_frequency_hz <= 0xFFFFFFFF:
            raise ValueError("HDSDR center frequency must fit in uint32")
        self.output_path = _wav_output_path(output_path, capture_format, self.center_frequency_hz)
        if self.output_path.exists():
            raise FileExistsError(f"capture output already exists: {self.output_path}")
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._queue: queue.Queue[IQBlock] = queue.Queue(maxsize=queue_blocks)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._stream: BinaryIO | None = None
        self._epoch: int | None = None
        self._data_size_offset = 0
        self._data_offset = 0
        self._auxi_offset: int | None = None
        self._started_at = datetime.now(timezone.utc)
        self.bytes_written = 0
        self.samples_written = 0
        self.incomplete = False
        self.reason: str | None = None
        self.finalized = False

    def start(self) -> None:
        self._stream = self.output_path.open("xb+")
        self._write_header()
        self._thread = threading.Thread(target=self._run, name="wav-recorder", daemon=True)
        self._thread.start()

    def _write_header(self) -> None:
        stream = self._stream
        stream.write(struct.pack("<4sI4s", b"RIFF", 0, b"WAVE"))
        stream.write(struct.pack(
            "<4sIHHIIHH",
            b"fmt ", 16, 1, 2, self.sample_rate_sps,
            self.sample_rate_sps * 4, 4, 16,
        ))
        if self.capture_format is CaptureFormat.HDSDR_WAV:
            self._auxi_offset = stream.tell() + 8
            auxi = (
                _system_time(self._started_at)
                + _system_time(self._started_at)
                + struct.pack(
                    "<9I",
                    self.center_frequency_hz,
                    self.sample_rate_sps,
                    0,
                    self.sample_rate_sps,
                    0,
                    0,
                    32767,
                    0,
                    0,
                )
                + bytes(96)
            )
            stream.write(struct.pack("<4sI", b"auxi", len(auxi)))
            stream.write(auxi)
        self._data_size_offset = stream.tell() + 4
        stream.write(struct.pack("<4sI", b"data", 0))
        self._data_offset = stream.tell()

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

    def _encode(self, block: IQBlock) -> bytes:
        raw = bytes(block.payload)
        if self.sample_format is SampleFormat.CS16:
            return raw
        values = np.frombuffer(raw, dtype="<f4")
        if not np.isfinite(values).all():
            raise ValueError("capture IQ float contains NaN or infinity")
        return np.clip(np.rint(values * 32767.0), -32768, 32767).astype("<i2").tobytes()

    def _run(self) -> None:
        try:
            max_data_bytes = 0xFFFFFFFF - (self._data_offset - 8)
            while not self._stop.is_set() or not self._queue.empty():
                try:
                    block = self._queue.get(timeout=.05)
                except queue.Empty:
                    continue
                try:
                    raw = self._encode(block)
                    if self.bytes_written + len(raw) > max_data_bytes:
                        self._fail("limite WAV 4 Gio atteinte")
                        break
                    written = self._stream.write(raw)
                    if written is not None and written != len(raw):
                        raise OSError("short recorder write")
                    self.bytes_written += len(raw)
                    self.samples_written += block.sample_count
                except (OSError, ValueError) as exc:
                    self._fail(f"écriture impossible: {exc}")
                    break
                finally:
                    self._queue.task_done()
        finally:
            self._finalize()

    def _finalize(self) -> None:
        stream = self._stream
        if stream is None:
            return
        try:
            stream.flush()
            stream.seek(4)
            stream.write(struct.pack("<I", self._data_offset + self.bytes_written - 8))
            stream.seek(self._data_size_offset)
            stream.write(struct.pack("<I", self.bytes_written))
            if self._auxi_offset is not None:
                stream.seek(self._auxi_offset + 16)
                stream.write(_system_time(datetime.now(timezone.utc)))
            stream.flush()
            os.fsync(stream.fileno())
            self.finalized = True
        except OSError:
            self.incomplete = True
        finally:
            stream.close()


Recorder = SigMFRecorder | WAVRecorder


def create_recorder(
    output_path: str | Path,
    sample_rate_sps: int,
    sample_format: SampleFormat,
    center_frequency_hz: int,
    capture_format: CaptureFormat | str = CaptureFormat.SIGMF,
) -> Recorder:
    selected = CaptureFormat(capture_format)
    if selected is CaptureFormat.SIGMF:
        return SigMFRecorder(output_path, sample_rate_sps, sample_format, center_frequency_hz)
    return WAVRecorder(
        output_path,
        sample_rate_sps,
        sample_format,
        center_frequency_hz,
        capture_format=selected,
    )


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
