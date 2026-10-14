from __future__ import annotations

import ctypes
from dataclasses import dataclass
from multiprocessing import shared_memory
from pathlib import Path
import struct
import sys
import threading
import time

from .model import (
    Discontinuity,
    IQBlock,
    SampleFormat,
    TimeDomain,
    TimestampOrigin,
)

MAGIC = b"SDBR"
VERSION = 2
HEADER_BYTES = 128
SLOT_HEADER_BYTES = 64
EMPTY = (1 << 64) - 1
GLOBAL = struct.Struct("<4sIIIIIIIQQ")
SLOT = struct.Struct("<IIQQQQIIQII")

FLAG_DISCONTINUITY = 1 << 0
FLAG_TIME_VALID = 1 << 1
FLAG_HARDWARE_ORIGIN = 1 << 2
FLAG_REPLAY = 1 << 3
_REASON_SHIFT = 8
_REASONS = {
    Discontinuity.NONE: 0,
    Discontinuity.START: 1,
    Discontinuity.RECONFIGURE: 2,
    Discontinuity.SOURCE_LOSS: 3,
    Discontinuity.RING_OVERRUN: 4,
    Discontinuity.DSP_DROP: 5,
    Discontinuity.REPLAY_SEEK: 6,
}
_REASONS_INV = {value: key for key, value in _REASONS.items()}


def _align64(value: int) -> int:
    return (value + 63) & ~63


class _AtomicGuards:
    def __init__(self) -> None:
        root = Path(__file__).resolve().parents[2]
        candidates = [
            root / "native" / "build" / "ring_atomic-x64" / "Release" / "sdr_ring_atomic.dll",
            Path(__file__).resolve().parent / "native" / "sdr_ring_atomic.dll",
            Path(sys.executable).resolve().parent / "native" / "sdr_ring_atomic.dll",
        ]
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            candidates.insert(0, Path(sys._MEIPASS) / "native" / "sdr_ring_atomic.dll")  # type: ignore[attr-defined]
        dll_path = next((item for item in candidates if item.exists()), None)
        if dll_path is None:
            raise RuntimeError("sdr_ring_atomic.dll x64 missing; run native/build_native.ps1")
        self.dll = ctypes.CDLL(str(dll_path))
        self.dll.sdb_guard_load.argtypes = [ctypes.c_void_p]
        self.dll.sdb_guard_load.restype = ctypes.c_uint32
        self.dll.sdb_guard_store.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        self.dll.sdb_guard_store.restype = None

    @staticmethod
    def _address(buffer: memoryview, offset: int) -> int:
        return ctypes.addressof(ctypes.c_ubyte.from_buffer(buffer, offset))

    def load(self, buffer: memoryview, offset: int) -> int:
        return int(self.dll.sdb_guard_load(self._address(buffer, offset)))

    def store(self, buffer: memoryview, offset: int, value: int) -> None:
        self.dll.sdb_guard_store(self._address(buffer, offset), ctypes.c_uint32(value))


_ATOMIC: _AtomicGuards | None = None
_ATOMIC_LOCK = threading.Lock()


def _atomic() -> _AtomicGuards:
    global _ATOMIC
    with _ATOMIC_LOCK:
        if _ATOMIC is None:
            _ATOMIC = _AtomicGuards()
        return _ATOMIC


@dataclass(frozen=True, slots=True)
class RingDescriptor:
    name: str
    slot_count: int
    slot_stride: int
    max_samples: int
    sample_format: SampleFormat
    source_id: str = "source-0"
    version: int = VERSION
    header_bytes: int = HEADER_BYTES

    @property
    def payload_bytes(self) -> int:
        return self.max_samples * self.sample_format.bytes_per_iq

    @property
    def block_samples(self) -> int:
        return self.max_samples

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "header_bytes": self.header_bytes,
            "slot_count": self.slot_count,
            "slot_stride": self.slot_stride,
            "max_samples": self.max_samples,
            "block_samples": self.max_samples,
            "payload_bytes": self.payload_bytes,
            "sample_format": self.sample_format.value,
            "source_id": self.source_id,
        }


class SharedIQRing:
    """SDBR v2 single-writer ring with guarded, owned-copy reads."""

    def __init__(
        self,
        slot_count: int,
        block_samples: int,
        *,
        sample_format: SampleFormat = SampleFormat.CS16,
        source_id: str = "source-0",
        name: str | None = None,
        create: bool = True,
    ):
        if slot_count < 4:
            raise ValueError("slot_count must be >= 4")
        if block_samples < 1:
            raise ValueError("block_samples must be positive")
        self.slot_count = int(slot_count)
        self.block_samples = int(block_samples)
        self.sample_format = SampleFormat(sample_format)
        self.source_id = str(source_id)
        self.payload_bytes = self.block_samples * self.sample_format.bytes_per_iq
        self.slot_stride = _align64(SLOT_HEADER_BYTES + self.payload_bytes)
        self.total_bytes = HEADER_BYTES + self.slot_count * self.slot_stride
        self._owner = create
        self._closed = False
        self._write_lock = threading.Lock()
        _atomic()
        self._shm = shared_memory.SharedMemory(name=name, create=create, size=self.total_bytes if create else 0)
        if create:
            self._shm.buf[:] = b"\0" * self.total_bytes
            GLOBAL.pack_into(
                self._shm.buf,
                0,
                MAGIC,
                VERSION,
                HEADER_BYTES,
                self.slot_count,
                self.slot_stride,
                self.block_samples,
                self.sample_format.wire_code,
                0,
                EMPTY,
                0,
            )
        else:
            fields = GLOBAL.unpack_from(self._shm.buf, 0)
            expected = (MAGIC, VERSION, HEADER_BYTES, self.slot_count, self.slot_stride, self.block_samples, self.sample_format.wire_code)
            if tuple(fields[:7]) != expected:
                self._shm.close()
                raise ValueError("shared ring descriptor mismatch")

    @classmethod
    def attach(cls, descriptor: RingDescriptor | dict) -> "SharedIQRing":
        if isinstance(descriptor, dict):
            version = int(descriptor.get("version", 1))
            if version != VERSION:
                raise ValueError(f"SDBR v{version} is not a v2 ring")
            fmt = SampleFormat(descriptor.get("sample_format", SampleFormat.CS16.value))
            return cls(
                int(descriptor["slot_count"]),
                int(descriptor.get("max_samples", descriptor["block_samples"])),
                sample_format=fmt,
                source_id=str(descriptor.get("source_id", "source-0")),
                name=str(descriptor["name"]),
                create=False,
            )
        return cls(
            descriptor.slot_count,
            descriptor.max_samples,
            sample_format=descriptor.sample_format,
            source_id=descriptor.source_id,
            name=descriptor.name,
            create=False,
        )

    @property
    def descriptor(self) -> RingDescriptor:
        return RingDescriptor(
            self._shm.name,
            self.slot_count,
            self.slot_stride,
            self.block_samples,
            self.sample_format,
            self.source_id,
        )

    def _read_latest(self) -> tuple[int, int]:
        atomic = _atomic()
        for _ in range(3):
            guard_before = atomic.load(self._shm.buf, 28)
            if guard_before & 1:
                continue
            latest, epoch = struct.unpack_from("<QQ", self._shm.buf, 32)
            guard_after = atomic.load(self._shm.buf, 28)
            if guard_before == guard_after and not (guard_after & 1):
                return latest, epoch
        return EMPTY, 0

    @property
    def latest_sequence(self) -> int:
        return self._read_latest()[0]

    @property
    def epoch(self) -> int:
        return self._read_latest()[1]

    def _offset(self, slot: int) -> int:
        return HEADER_BYTES + slot * self.slot_stride

    @staticmethod
    def _flags(block: IQBlock) -> int:
        flags = _REASONS[block.discontinuity] << _REASON_SHIFT
        if block.discontinuity is not Discontinuity.NONE:
            flags |= FLAG_DISCONTINUITY
        if block.time_domain is not TimeDomain.UNKNOWN:
            flags |= FLAG_TIME_VALID
        if block.timestamp_origin is TimestampOrigin.HARDWARE:
            flags |= FLAG_HARDWARE_ORIGIN
        if block.time_domain is TimeDomain.REPLAY_RELATIVE:
            flags |= FLAG_REPLAY
        return flags

    def write(self, block: IQBlock | int, *legacy) -> None:
        if isinstance(block, int):
            if len(legacy) != 4:
                raise TypeError("legacy write expects timestamp, revision, count, payload")
            legacy_sequence = block
            timestamp_ns, revision, sample_count, payload = legacy
            block = IQBlock(
                source_id=self.source_id,
                epoch=1,
                sequence=legacy_sequence,
                first_sample_index=legacy_sequence * int(sample_count),
                sample_count=int(sample_count),
                sample_rate_sps=2_000_000,
                center_frequency_hz=144_300_000,
                config_revision=int(revision),
                sample_format=self.sample_format,
                timestamp_ns=int(timestamp_ns),
                time_domain=TimeDomain.HOST_MONOTONIC,
                timestamp_origin=TimestampOrigin.HOST_OBSERVATION,
                discontinuity=Discontinuity.START if legacy_sequence == 0 else Discontinuity.NONE,
                lost_samples=0,
                payload=memoryview(payload),
            )
        if block.source_id != self.source_id:
            raise ValueError("block source_id does not match ring")
        if block.sample_format is not self.sample_format:
            raise ValueError("block format does not match ring")
        if block.sample_count > self.block_samples:
            raise ValueError("payload exceeds ring slot")
        slot = block.sequence % self.slot_count
        offset = self._offset(slot)
        atomic = _atomic()
        with self._write_lock:
            guard = atomic.load(self._shm.buf, offset)
            odd = (guard + 1) | 1
            atomic.store(self._shm.buf, offset, odd)
            SLOT.pack_into(
                self._shm.buf,
                offset,
                odd,
                block.sample_count,
                block.sequence,
                block.first_sample_index,
                block.timestamp_ns,
                block.epoch,
                block.config_revision,
                block.sample_rate_sps,
                block.center_frequency_hz,
                self._flags(block),
                int(block.time_domain),
            )
            start = offset + SLOT_HEADER_BYTES
            self._shm.buf[start:start + len(block.payload)] = block.payload
            even = odd + 1
            atomic.store(self._shm.buf, offset, even)
            header_guard = atomic.load(self._shm.buf, 28)
            header_odd = (header_guard + 1) | 1
            atomic.store(self._shm.buf, 28, header_odd)
            struct.pack_into("<QQ", self._shm.buf, 32, block.sequence, block.epoch)
            atomic.store(self._shm.buf, 28, header_odd + 1)

    def read(self, sequence: int, *, copy: bool = True) -> IQBlock | None:
        if not copy:
            raise ValueError("SDBR v2 exposes owned copies only")
        offset = self._offset(sequence % self.slot_count)
        atomic = _atomic()
        for _ in range(3):
            guard_before = atomic.load(self._shm.buf, offset)
            if guard_before & 1:
                continue
            fields = SLOT.unpack_from(self._shm.buf, offset)
            (_, count, actual_sequence, first_index, timestamp, epoch, revision, rate, frequency, flags, time_domain) = fields
            if actual_sequence != sequence or count < 1 or count > self.block_samples:
                return None
            length = count * self.sample_format.bytes_per_iq
            start = offset + SLOT_HEADER_BYTES
            payload = bytes(self._shm.buf[start:start + length])
            guard_after = atomic.load(self._shm.buf, offset)
            if guard_before == guard_after and not (guard_after & 1):
                reason = _REASONS_INV.get((flags >> _REASON_SHIFT) & 0xFF, Discontinuity.NONE)
                origin = TimestampOrigin.HARDWARE if flags & FLAG_HARDWARE_ORIGIN else TimestampOrigin.HOST_OBSERVATION
                if flags & FLAG_REPLAY:
                    origin = TimestampOrigin.DERIVED
                return IQBlock(
                    source_id=self.source_id,
                    epoch=epoch,
                    sequence=actual_sequence,
                    first_sample_index=first_index,
                    sample_count=count,
                    sample_rate_sps=rate,
                    center_frequency_hz=frequency,
                    config_revision=revision,
                    sample_format=self.sample_format,
                    timestamp_ns=timestamp,
                    time_domain=TimeDomain(time_domain),
                    timestamp_origin=origin,
                    discontinuity=reason,
                    lost_samples=None if reason is Discontinuity.SOURCE_LOSS else 0,
                    payload=memoryview(payload),
                )
        return None

    def close(self, unlink: bool = False) -> None:
        if self._closed:
            return
        self._closed = True
        self._shm.close()
        if unlink and self._owner:
            try:
                self._shm.unlink()
            except FileNotFoundError:
                pass


class RingReader:
    def __init__(self, ring: SharedIQRing, start_at_latest: bool = True):
        self.ring = ring
        latest = ring.latest_sequence
        self.next_sequence = 0 if latest == EMPTY else (latest + 1 if start_at_latest else max(0, latest - ring.slot_count + 1))
        self.dropped_blocks = 0
        self.torn_retries_exhausted = 0

    def read(self, timeout: float = 1.0) -> IQBlock | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            latest = self.ring.latest_sequence
            if latest != EMPTY and latest >= self.next_sequence:
                oldest = max(0, latest - self.ring.slot_count + 1)
                if self.next_sequence < oldest:
                    self.dropped_blocks += oldest - self.next_sequence
                    self.next_sequence = oldest
                block = self.ring.read(self.next_sequence)
                if block is not None:
                    self.next_sequence += 1
                    return block
                self.torn_retries_exhausted += 1
                self.next_sequence += 1
                self.dropped_blocks += 1
            time.sleep(0.001)
        return None

    def sync_latest(self) -> None:
        """Discard stale data and resume at the newest complete block."""
        latest = self.ring.latest_sequence
        self.next_sequence = 0 if latest == EMPTY else latest + 1


class LegacyV1RingReader:
    """Lecteur de transition SDBR v1 ; aucune émission v1 n'est créée ici."""

    GLOBAL = struct.Struct("<4sIIIIQ")
    SLOT = struct.Struct("<QQIIQ")

    def __init__(self, name: str, slot_count: int, block_samples: int, source_id: str = "legacy-v1"):
        self.shm = shared_memory.SharedMemory(name=name, create=False)
        self.slot_count = slot_count
        self.block_samples = block_samples
        self.payload_bytes = block_samples * 4
        self.slot_bytes = self.SLOT.size + self.payload_bytes
        magic, version, slots, payload, header, latest = self.GLOBAL.unpack_from(self.shm.buf, 0)
        if (magic, version, slots, payload, header) != (MAGIC, 1, slot_count, self.payload_bytes, self.SLOT.size):
            self.shm.close()
            raise ValueError("invalid SDBR v1 descriptor")
        self.next_sequence = 0 if latest == EMPTY else latest + 1
        self.source_id = source_id

    def close(self) -> None:
        self.shm.close()
