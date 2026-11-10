from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import struct
import threading
import time

import numpy as np

from .model import (
    DeviceCapabilities,
    DeviceDescriptor,
    Discontinuity,
    MAX_CENTER_FREQUENCY_HZ,
    RadioConfig,
    SampleFormat,
    TimeDomain,
    TimestampOrigin,
)
from .source import BlockCallback, ErrorCallback, IQSource, SourceChunk


@dataclass(frozen=True, slots=True)
class WAVIQInfo:
    path: Path
    data_offset: int
    data_bytes: int
    sample_count: int
    sample_rate_sps: int
    center_frequency_hz: int | None
    codec: int
    bits_per_sample: int
    block_align: int

    @property
    def input_kind(self) -> str:
        if self.codec == 3:
            return "float32"
        return {8: "uint8", 16: "int16", 32: "int32"}[self.bits_per_sample]

    @property
    def output_format(self) -> SampleFormat:
        # SDRbridge keeps one stable CS16 ring so a file can replace a live
        # SDR without disconnecting local readers. Wider recordings are
        # converted once at ingestion.
        return SampleFormat.CS16


_FREQUENCY_RE = re.compile(r"(?<!\d)(\d+(?:\.\d+)?)\s*(GHz|MHz|kHz|Hz)", re.IGNORECASE)


def frequency_from_filename(path: str | Path) -> int | None:
    matches = list(_FREQUENCY_RE.finditer(Path(path).stem))
    if not matches:
        return None
    value = float(matches[-1].group(1))
    unit = matches[-1].group(2).lower()
    multiplier = {"hz": 1, "khz": 1_000, "mhz": 1_000_000, "ghz": 1_000_000_000}[unit]
    frequency = round(value * multiplier)
    return frequency if frequency > 0 else None


def inspect_iq_wav(path: str | Path) -> WAVIQInfo:
    wav_path = Path(path)
    file_size = wav_path.stat().st_size
    with wav_path.open("rb") as stream:
        header = stream.read(12)
        if len(header) != 12 or header[:4] not in {b"RIFF", b"RF64"} or header[8:] != b"WAVE":
            raise ValueError("IQ file must be a RIFF/RF64 WAVE file")
        rf64 = header[:4] == b"RF64"
        rf64_data_bytes: int | None = None
        auxi_center_frequency_hz: int | None = None
        fmt: tuple[int, int, int, int, int] | None = None
        data_offset: int | None = None
        data_bytes: int | None = None
        while stream.tell() + 8 <= file_size:
            chunk_header = stream.read(8)
            if len(chunk_header) != 8:
                break
            chunk_id, chunk_size = struct.unpack("<4sI", chunk_header)
            chunk_start = stream.tell()
            if chunk_id == b"ds64":
                body = stream.read(min(chunk_size, 28))
                if len(body) < 24:
                    raise ValueError("truncated RF64 ds64 chunk")
                _riff_size, rf64_data_bytes, _sample_count = struct.unpack_from("<QQQ", body)
            elif chunk_id == b"fmt ":
                body = stream.read(chunk_size)
                if len(body) < 16:
                    raise ValueError("truncated WAVE fmt chunk")
                codec, channels, rate, _byte_rate, block_align, bits = struct.unpack_from("<HHIIHH", body)
                if codec == 0xFFFE:
                    if len(body) < 40:
                        raise ValueError("truncated extensible WAVE fmt chunk")
                    codec = struct.unpack_from("<H", body, 24)[0]
                fmt = (codec, channels, rate, block_align, bits)
            elif chunk_id == b"auxi":
                # SpectraVue/HDSDR AUXINFO: two 16-byte SYSTEMTIME
                # structures followed by the uint32 receiver centre.
                body = stream.read(min(chunk_size, 36))
                if len(body) >= 36:
                    candidate = struct.unpack_from("<I", body, 32)[0]
                    if 1_000 <= candidate <= MAX_CENTER_FREQUENCY_HZ:
                        auxi_center_frequency_hz = candidate
            elif chunk_id == b"data":
                data_offset = chunk_start
                data_bytes = rf64_data_bytes if rf64 and chunk_size == 0xFFFFFFFF else chunk_size
                break
            stream.seek(chunk_start + chunk_size + (chunk_size & 1))

    if fmt is None or data_offset is None or data_bytes is None:
        raise ValueError("WAVE IQ file requires fmt and data chunks")
    codec, channels, rate, block_align, bits = fmt
    if channels != 2:
        raise ValueError("WAVE IQ file must contain exactly two channels (I and Q)")
    if codec not in {1, 3} or (codec == 1 and bits not in {8, 16, 32}) or (codec == 3 and bits != 32):
        raise ValueError("unsupported WAVE IQ encoding; use uint8/int16/int32 PCM or float32")
    expected_align = channels * (bits // 8)
    if block_align != expected_align or rate <= 0:
        raise ValueError("invalid WAVE IQ format geometry")
    if data_bytes <= 0 or data_bytes % block_align:
        raise ValueError("WAVE IQ data ends with a partial complex sample")
    if data_offset + data_bytes > file_size:
        raise ValueError("truncated WAVE IQ data chunk")
    return WAVIQInfo(
        wav_path, data_offset, data_bytes, data_bytes // block_align, rate,
        auxi_center_frequency_hz or frequency_from_filename(wav_path), codec, bits, block_align,
    )


class IQFileSource(IQSource):
    DEVICE_PREFIX = "file:"

    def __init__(
        self,
        path: str | Path,
        block_samples: int = 4096,
        *,
        center_frequency_hz: int | None = None,
        realtime: bool = True,
        loop: bool = False,
    ):
        self.path = Path(path)
        self.block_samples = int(block_samples)
        self.center_frequency_override_hz = int(center_frequency_hz) if center_frequency_hz is not None else None
        self.realtime = bool(realtime)
        self.loop = bool(loop)
        self.info: WAVIQInfo | None = None
        self._config: RadioConfig | None = None
        self._position = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._on_block: BlockCallback | None = None
        self._on_error: ErrorCallback | None = None
        self._seek_pending = False
        self._loop_pending = False
        self.eof = False

    @property
    def name(self) -> str:
        kind = self.info.input_kind if self.info else "WAV"
        return f"Fichier IQ {kind} — {self.path.name}"

    @property
    def device_id(self) -> str:
        return self.DEVICE_PREFIX + str(self.path.resolve())

    def enumerate(self) -> list[DeviceDescriptor]:
        if not self.path.is_file():
            return []
        return [DeviceDescriptor(self.device_id, "file/wav", self.name)]

    def open(self, device_id: str | None = None) -> None:
        if device_id is not None and device_id != self.device_id:
            raise KeyError(device_id)
        self.info = inspect_iq_wav(self.path)
        frequency = self.center_frequency_override_hz or self.info.center_frequency_hz
        if frequency is None:
            raise ValueError("center frequency is absent from the filename; configure iq_file.center_frequency_hz")
        self._config = RadioConfig(
            center_frequency_hz=frequency,
            sample_rate_sps=self.info.sample_rate_sps,
            bandwidth_hz=self.info.sample_rate_sps,
            gain_reduction_db=0,
            agc_enabled=False,
            sample_format=self.info.output_format,
        )
        self._position = 0
        self.eof = False

    def capabilities(self, device_id: str) -> DeviceCapabilities:
        if self._config is None:
            self.open(device_id)
        cfg = self._config
        return DeviceCapabilities(
            device_id, ((cfg.center_frequency_hz, cfg.center_frequency_hz + 1),),
            (cfg.sample_rate_sps,), (cfg.bandwidth_hz,), (), {}, False, (cfg.sample_format,),
        )

    def configure(self, request: RadioConfig) -> RadioConfig:
        if self._config is None:
            raise RuntimeError("IQ file source is not open")
        self._config = RadioConfig(
            self._config.center_frequency_hz,
            self._config.sample_rate_sps,
            self._config.bandwidth_hz,
            0,
            False,
            sample_format=self._config.sample_format,
            revision=request.revision,
        )
        return self._config

    def start(self, on_block: BlockCallback, on_error: ErrorCallback | None = None) -> None:
        if self._config is None or self.info is None:
            raise RuntimeError("IQ file source is not open")
        if self._thread and self._thread.is_alive():
            raise RuntimeError("IQ file replay already started")
        self._on_block, self._on_error = on_block, on_error
        self._stop.clear()
        self.eof = False
        self._thread = threading.Thread(target=self._run, name="iq-file-replay", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)
            if self._thread.is_alive():
                raise RuntimeError("IQ file replay did not stop")
        self._thread = None

    def close(self) -> None:
        self.stop()
        self.info = None
        self._config = None

    def seek(self, sample_index: int) -> None:
        if self.info is None or not 0 <= sample_index <= self.info.sample_count:
            raise ValueError("IQ file seek out of range")
        self._position = int(sample_index)
        self._seek_pending = True
        self.eof = False

    def _convert(self, raw: bytes) -> memoryview:
        kind = self.info.input_kind
        if kind == "int16":
            return memoryview(raw)
        if kind == "uint8":
            values = (np.frombuffer(raw, dtype=np.uint8).astype(np.int16) - 128) << 8
            return memoryview(values.astype("<i2", copy=False)).cast("B")
        if kind == "int32":
            pairs = np.frombuffer(raw, dtype="<i4").reshape(-1, 2).astype(np.float32)
            pairs *= np.float32(1.0 / 2_147_483_648.0)
        else:
            pairs = np.frombuffer(raw, dtype="<f4").reshape(-1, 2)
            if not np.isfinite(pairs).all():
                raise ValueError("WAVE IQ float data contains NaN or infinity")
        output = np.clip(np.rint(pairs * 32768.0), -32768, 32767).astype("<i2")
        return memoryview(output).cast("B")

    def _run(self) -> None:
        try:
            next_deadline = time.perf_counter()
            with self.path.open("rb") as stream:
                while not self._stop.is_set():
                    if self._position >= self.info.sample_count:
                        if not self.loop:
                            self.eof = True
                            break
                        self._position = 0
                        self._loop_pending = True
                        next_deadline = time.perf_counter()
                    position = self._position
                    count = min(self.block_samples, self.info.sample_count - position)
                    stream.seek(self.info.data_offset + position * self.info.block_align)
                    raw = stream.read(count * self.info.block_align)
                    if len(raw) != count * self.info.block_align:
                        raise OSError("truncated WAVE IQ data during replay")
                    discontinuity = (
                        Discontinuity.REPLAY_SEEK if self._seek_pending or self._loop_pending
                        else (Discontinuity.START if position == 0 else Discontinuity.NONE)
                    )
                    self._seek_pending = self._loop_pending = False
                    self._on_block(SourceChunk(
                        self._convert(raw), count, position,
                        round(position * 1_000_000_000 / self._config.sample_rate_sps),
                        TimeDomain.REPLAY_RELATIVE, TimestampOrigin.DERIVED, discontinuity, 0,
                    ))
                    self._position += count
                    if self.realtime:
                        next_deadline += count / self._config.sample_rate_sps
                        self._stop.wait(max(0.0, next_deadline - time.perf_counter()))
        except BaseException as exc:
            if self._on_error and not self._stop.is_set():
                self._on_error(exc)
