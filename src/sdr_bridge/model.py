from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum, IntEnum
import time
from typing import Any, Mapping


class SampleFormat(str, Enum):
    CS16 = "ci16_le"
    CF32 = "cf32_le"
    S16LE_IQ = "ci16_le"  # nom historique conservé

    @property
    def bytes_per_iq(self) -> int:
        return 4 if self is SampleFormat.CS16 else 8

    @property
    def wire_code(self) -> int:
        return 1 if self is SampleFormat.CS16 else 2

    @classmethod
    def from_wire_code(cls, value: int) -> "SampleFormat":
        if value == 1:
            return cls.CS16
        if value == 2:
            return cls.CF32
        raise ValueError("unknown sample format")


class LifecycleState(str, Enum):
    IDLE = "IDLE"
    OPENING = "OPENING"
    READY = "READY"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    RECONFIGURING = "RECONFIGURING"
    STOPPING = "STOPPING"
    RECOVERING = "RECOVERING"
    ERROR = "ERROR"


class TimeDomain(IntEnum):
    UNKNOWN = 0
    DEVICE_RELATIVE = 1
    HOST_MONOTONIC = 2
    UNIX_UTC = 3
    REPLAY_RELATIVE = 4


class TimestampOrigin(str, Enum):
    HARDWARE = "hardware"
    HOST_OBSERVATION = "host_observation"
    DERIVED = "derived"


class Discontinuity(str, Enum):
    NONE = "none"
    START = "start"
    RECONFIGURE = "reconfigure"
    SOURCE_LOSS = "source_loss"
    RING_OVERRUN = "ring_overrun"
    DSP_DROP = "dsp_drop"
    REPLAY_SEEK = "replay_seek"


@dataclass(frozen=True, slots=True)
class RadioConfig:
    center_frequency_hz: int = 144_300_000
    sample_rate_sps: int = 2_000_000
    bandwidth_hz: int = 1_536_000
    gain_reduction_db: int = 40
    agc_enabled: bool = False
    antenna: str | None = None
    gains: Mapping[str, float] = field(default_factory=dict)
    sample_format: SampleFormat = SampleFormat.CS16
    revision: int = 1

    def validate(self) -> None:
        if not 1_000 <= self.center_frequency_hz <= 2_000_000_000:
            raise ValueError("center_frequency_hz out of supported bridge range")
        if not 1 <= self.sample_rate_sps <= 20_000_000:
            raise ValueError("sample_rate_sps out of supported bridge range")
        if not 1 <= self.bandwidth_hz <= self.sample_rate_sps:
            raise ValueError("bandwidth_hz must be positive and <= sample_rate_sps")
        if not 0 <= self.gain_reduction_db <= 100:
            raise ValueError("gain_reduction_db out of range")
        if self.revision < 1:
            raise ValueError("revision must be positive")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["sample_format"] = self.sample_format.value
        data["gains"] = dict(self.gains)
        return data


EffectiveConfig = RadioConfig


@dataclass(frozen=True, slots=True)
class DeviceDescriptor:
    device_id: str
    backend: str
    model: str
    serial: str | None = None
    rx_channels: int = 1
    available: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DeviceCapabilities:
    device_id: str
    frequency_ranges_hz: tuple[tuple[int, int], ...]
    sample_rates_sps: tuple[int, ...]
    bandwidths_hz: tuple[int, ...]
    antennas: tuple[str, ...] = ()
    gain_ranges: Mapping[str, tuple[float, float]] = field(default_factory=dict)
    agc_available: bool = False
    formats: tuple[SampleFormat, ...] = (SampleFormat.CS16,)
    read_revision: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "formats": [item.value for item in self.formats],
            "gain_ranges": {key: list(value) for key, value in self.gain_ranges.items()},
        }


@dataclass(frozen=True, slots=True)
class StreamProfile:
    profile_id: str
    profile_revision: int
    output_rate_sps: int
    sample_format: SampleFormat
    protocol: str
    center_offset_hz: int = 0
    name: str = ""

    def validate(self, source_rate_sps: int | None = None) -> None:
        if not self.profile_id or self.profile_revision < 1:
            raise ValueError("invalid profile identity")
        if self.output_rate_sps <= 0:
            raise ValueError("output_rate_sps must be positive")
        if source_rate_sps is not None and self.output_rate_sps > source_rate_sps:
            raise ValueError("upsampling is not supported in V1")
        if self.center_offset_hz != 0:
            raise ValueError("center offset is not supported in V1")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["sample_format"] = self.sample_format.value
        return data


@dataclass(frozen=True, slots=True)
class IQBlock:
    source_id: str
    epoch: int
    sequence: int
    first_sample_index: int
    sample_count: int
    sample_rate_sps: int
    center_frequency_hz: int
    config_revision: int
    sample_format: SampleFormat
    timestamp_ns: int
    time_domain: TimeDomain
    timestamp_origin: TimestampOrigin
    discontinuity: Discontinuity
    lost_samples: int | None
    payload: memoryview

    def __post_init__(self) -> None:
        if self.sample_count <= 0:
            raise ValueError("sample_count must be positive")
        if len(self.payload) != self.sample_count * self.sample_format.bytes_per_iq:
            raise ValueError("payload length does not match sample_count/format")


@dataclass(slots=True)
class ClientStats:
    client_id: str
    name: str
    connected_since_ns: int = field(default_factory=time.monotonic_ns)
    blocks_read: int = 0
    samples_read: int = 0
    dropped_blocks: int = 0
    last_sequence: int = -1
    last_seen_ns: int = field(default_factory=time.monotonic_ns)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
