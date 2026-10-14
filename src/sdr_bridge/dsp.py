from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
import math

import numpy as np
from scipy import signal

from .model import (
    Discontinuity,
    IQBlock,
    SampleFormat,
    TimestampOrigin,
)


def payload_to_complex(payload: memoryview | bytes, sample_format: SampleFormat) -> np.ndarray:
    if sample_format is SampleFormat.CS16:
        scalars = np.frombuffer(payload, dtype="<i2")
        if len(scalars) % 2:
            raise ValueError("CS16 payload has a partial IQ sample")
        pairs = scalars.reshape(-1, 2).astype(np.float32)
        return ((pairs[:, 0] + 1j * pairs[:, 1]) / 32768.0).astype(np.complex64)
    scalars = np.frombuffer(payload, dtype="<f4")
    if len(scalars) % 2:
        raise ValueError("CF32 payload has a partial IQ sample")
    if not np.isfinite(scalars).all():
        raise ValueError("CF32 payload contains NaN or infinity")
    pairs = scalars.reshape(-1, 2)
    return (pairs[:, 0] + 1j * pairs[:, 1]).astype(np.complex64)


def complex_to_payload(values: np.ndarray, sample_format: SampleFormat) -> bytes:
    data = np.asarray(values)
    if not np.isfinite(data.real).all() or not np.isfinite(data.imag).all():
        raise ValueError("non-finite DSP sample")
    if sample_format is SampleFormat.CF32:
        output = np.empty((len(data), 2), dtype="<f4")
        output[:, 0] = data.real
        output[:, 1] = data.imag
        return output.tobytes()
    output = np.empty((len(data), 2), dtype="<i2")
    output[:, 0] = np.clip(np.rint(data.real * 32768.0), -32768, 32767).astype("<i2")
    output[:, 1] = np.clip(np.rint(data.imag * 32768.0), -32768, 32767).astype("<i2")
    return output.tobytes()


@dataclass(frozen=True, slots=True)
class FilterCharacterization:
    taps: int
    up: int
    down: int
    group_delay_input_samples: float
    group_delay_seconds: float
    passband_ripple_db: float
    stopband_attenuation_db: float


@lru_cache(maxsize=16)
def design_resampler_filter(input_rate: int, output_rate: int) -> tuple[np.ndarray, FilterCharacterization]:
    if input_rate <= 0 or output_rate <= 0 or output_rate > input_rate:
        raise ValueError("V1 requires 0 < output_rate <= input_rate")
    fraction = Fraction(output_rate, input_rate)
    up, down = fraction.numerator, fraction.denominator
    design_rate = input_rate * up
    transition_hz = 0.10 * output_rate
    width = transition_hz / (design_rate / 2.0)
    attenuation_target = 80.0
    beta = 0.1102 * (attenuation_target - 8.7)
    taps = int(math.ceil((attenuation_target - 7.95) / (2.285 * math.pi * width))) + 1
    taps = max(taps, 31)
    if taps % 2 == 0:
        taps += 1
    for _ in range(8):
        centered = np.arange(taps, dtype=np.float64) - (taps - 1) / 2.0
        normalized_cutoff = 0.45 * output_rate / design_rate
        coefficients = 2.0 * normalized_cutoff * np.sinc(2.0 * normalized_cutoff * centered)
        coefficients *= np.kaiser(taps, beta)
        coefficients /= np.sum(coefficients)
        fft_size = 524288
        response = np.fft.rfft(coefficients, n=fft_size)
        frequencies = np.fft.rfftfreq(fft_size, d=1.0 / design_rate)
        passband = np.abs(response[frequencies <= 0.40 * output_rate])
        stopband = np.abs(response[frequencies >= 0.50 * output_rate])
        passband_db = 20.0 * np.log10(np.maximum(passband, 1e-300))
        stopband_db = 20.0 * np.log10(max(float(np.max(stopband)), 1e-300))
        ripple = float(np.max(passband_db) - np.min(passband_db))
        attenuation = float(-stopband_db)
        if ripple <= 0.1 and attenuation >= 80.0:
            break
        taps += 256
        if taps % 2 == 0:
            taps += 1
    else:
        raise RuntimeError("unable to meet FIR response target")
    coefficients *= up
    delay_high_rate = (taps - 1) / 2.0
    characterization = FilterCharacterization(
        taps=taps,
        up=up,
        down=down,
        group_delay_input_samples=delay_high_rate / up,
        group_delay_seconds=delay_high_rate / design_rate,
        passband_ripple_db=ripple,
        stopband_attenuation_db=attenuation,
    )
    return coefficients, characterization


class StreamingRationalResampler:
    """FIR rationnel causal, réalisé avec upfirdn et historique inter-blocs."""

    def __init__(self, input_rate: int, output_rate: int):
        self.input_rate = int(input_rate)
        self.output_rate = int(output_rate)
        self.taps, self.characterization = design_resampler_filter(input_rate, output_rate)
        self.up = self.characterization.up
        self.down = self.characterization.down
        self._history_inputs = int(math.ceil((len(self.taps) - 1) / self.up))
        self._history_capacity = self._history_inputs + self.down
        self.reset()

    def reset(self) -> None:
        self._history = np.empty(0, dtype=np.complex64)
        self._input_seen = 0
        self._next_output_index = 0

    def process(self, values: np.ndarray) -> np.ndarray:
        data = np.asarray(values, dtype=np.complex64)
        if not len(data):
            return np.empty(0, dtype=np.complex64)
        start_input = self._input_seen
        history = self._history
        available_base = start_input - len(history)
        if start_input < self._history_inputs:
            base_input = 0
        else:
            base_input = ((start_input - self._history_inputs) // self.down) * self.down
        base_input = max(base_input, available_base)
        selected_history = history[base_input - available_base:] if len(history) else history
        combined = np.concatenate((selected_history, data)) if len(selected_history) else data
        decimated = signal.upfirdn(self.taps, combined, up=self.up, down=self.down)
        base_output = base_input * self.up // self.down
        final_output = ((start_input + len(data)) * self.up + self.down - 1) // self.down
        first_output = max(self._next_output_index, base_output)
        local_start = first_output - base_output
        local_stop = final_output - base_output
        output = decimated[local_start:local_stop].astype(np.complex64, copy=False)
        self._next_output_index = final_output
        self._input_seen += len(data)
        keep = min(self._history_capacity, len(combined))
        self._history = combined[-keep:].copy()
        return output


class DSPPipeline:
    def __init__(self, source_id: str, input_rate: int, input_format: SampleFormat, output_rate: int, output_format: SampleFormat):
        self.source_id = source_id
        self.input_rate = int(input_rate)
        self.input_format = input_format
        self.output_rate = int(output_rate)
        self.output_format = output_format
        self.resampler = None if input_rate == output_rate else StreamingRationalResampler(input_rate, output_rate)
        self.epoch: int | None = None
        self.sequence = 0
        self.first_sample_index = 0
        self.blocks_processed = 0
        self.samples_produced = 0
        self.errors = 0

    @property
    def group_delay_seconds(self) -> float:
        return 0.0 if self.resampler is None else self.resampler.characterization.group_delay_seconds

    def process(self, block: IQBlock) -> IQBlock | None:
        if block.source_id != self.source_id:
            raise ValueError("pipeline source mismatch")
        reset = self.epoch != block.epoch or block.discontinuity is not Discontinuity.NONE
        if reset:
            self.epoch = block.epoch
            self.sequence = 0
            self.first_sample_index = 0
            if self.resampler:
                self.resampler.reset()
        try:
            values = payload_to_complex(block.payload, block.sample_format)
            output = values if self.resampler is None else self.resampler.process(values)
            if not len(output):
                return None
            payload = complex_to_payload(output, self.output_format)
        except Exception:
            self.errors += 1
            raise
        discontinuity = block.discontinuity if reset else Discontinuity.NONE
        timestamp = block.timestamp_ns
        origin = block.timestamp_origin
        if self.group_delay_seconds and block.time_domain.value:
            timestamp += int(round(self.group_delay_seconds * 1_000_000_000))
            origin = TimestampOrigin.DERIVED
        result = IQBlock(
            source_id=block.source_id,
            epoch=block.epoch,
            sequence=self.sequence,
            first_sample_index=self.first_sample_index,
            sample_count=len(output),
            sample_rate_sps=self.output_rate,
            center_frequency_hz=block.center_frequency_hz,
            config_revision=block.config_revision,
            sample_format=self.output_format,
            timestamp_ns=timestamp,
            time_domain=block.time_domain,
            timestamp_origin=origin,
            discontinuity=discontinuity,
            lost_samples=block.lost_samples,
            payload=memoryview(payload),
        )
        self.sequence += 1
        self.first_sample_index += len(output)
        self.blocks_processed += 1
        self.samples_produced += len(output)
        return result
