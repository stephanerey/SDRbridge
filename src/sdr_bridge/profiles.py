from __future__ import annotations

from dataclasses import dataclass, field
import threading
import uuid
from typing import Callable

from .dsp import DSPPipeline
from .model import IQBlock, SampleFormat, StreamProfile


DEFAULT_PROFILES = (
    StreamProfile("master-cs16", 1, 2_000_000, SampleFormat.CS16, "ring_v2", name="Master CS16"),
    StreamProfile("antrack-192k", 1, 192_000, SampleFormat.CS16, "ring_v2", name="ANTRACK 192 kS/s"),
    StreamProfile("antrack-96k", 1, 96_000, SampleFormat.CS16, "ring_v2", name="ANTRACK 96 kS/s"),
    StreamProfile("native-cf32-192k", 1, 192_000, SampleFormat.CF32, "sdbu_v2", name="Natif CF32 192 kS/s"),
    StreamProfile("native-cs16-192k", 1, 192_000, SampleFormat.CS16, "sdbu_v2", name="Natif CS16 192 kS/s"),
    StreamProfile("sdrpp-raw-192k", 1, 192_000, SampleFormat.CS16, "sdrpp_raw_cs16", name="SDR++ raw 192 kS/s"),
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


class PipelinePool:
    def __init__(self, source_id: str, input_rate: int, input_format: SampleFormat):
        self.source_id = source_id
        self.input_rate = input_rate
        self.input_format = input_format
        self._lock = threading.RLock()
        self._pipelines: dict[tuple, _SharedPipeline] = {}

    def _key(self, profile: StreamProfile) -> tuple:
        return (self.source_id, self.input_rate, self.input_format, profile.output_rate_sps, profile.sample_format, profile.center_offset_hz)

    def subscribe(self, profile: StreamProfile, callback: Callable[[IQBlock], None]) -> tuple[str, DSPPipeline]:
        profile.validate(self.input_rate)
        key = self._key(profile)
        with self._lock:
            shared = self._pipelines.get(key)
            if shared is None:
                shared = _SharedPipeline(DSPPipeline(self.source_id, self.input_rate, self.input_format, profile.output_rate_sps, profile.sample_format), profile=profile)
                self._pipelines[key] = shared
            token = uuid.uuid4().hex
            shared.consumers[token] = callback
            return token, shared.processor

    def unsubscribe(self, token: str) -> bool:
        with self._lock:
            for key, shared in list(self._pipelines.items()):
                if token in shared.consumers:
                    del shared.consumers[token]
                    if not shared.consumers:
                        del self._pipelines[key]
                    return True
        return False

    def process(self, block: IQBlock) -> None:
        with self._lock:
            pipelines = list(self._pipelines.values())
            # Garder le verrou pendant l'émission protège les rings de profil
            # contre un unsubscribe concurrent qui les fermerait alors qu'un
            # callback est encore en train d'écrire.
            for shared in pipelines:
                output = shared.processor.process(block)
                if output is None:
                    continue
                for callback in list(shared.consumers.values()):
                    callback(output)

    @property
    def pipeline_count(self) -> int:
        with self._lock:
            return len(self._pipelines)

    def reconfigure(self, input_rate: int, input_format: SampleFormat) -> None:
        with self._lock:
            existing = [(shared.profile, dict(shared.consumers)) for shared in self._pipelines.values()]
            self.input_rate = int(input_rate)
            self.input_format = input_format
            self._pipelines.clear()
            for profile, consumers in existing:
                if profile is None:
                    continue
                profile.validate(self.input_rate)
                key = self._key(profile)
                self._pipelines[key] = _SharedPipeline(
                    DSPPipeline(self.source_id, self.input_rate, self.input_format, profile.output_rate_sps, profile.sample_format),
                    consumers,
                    profile,
                )

    def snapshot(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "output_rate_sps": shared.processor.output_rate,
                    "output_format": shared.processor.output_format.value,
                    "subscribers": len(shared.consumers),
                    "blocks_processed": shared.processor.blocks_processed,
                    "samples_produced": shared.processor.samples_produced,
                    "group_delay_seconds": shared.processor.group_delay_seconds,
                    "errors": shared.processor.errors,
                }
                for shared in self._pipelines.values()
            ]
