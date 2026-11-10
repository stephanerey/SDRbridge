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


@lru_cache(maxsize=32)
def design_fractional_decimator_filters(
    input_rate: int,
    output_rate: int,
) -> tuple[np.ndarray, np.ndarray, FilterCharacterization]:
    """Design an efficient two-stage rational downsampler.

    A monolithic FIR for ratios such as 10 MS/s -> 4 MS/s has to provide a
    narrow 80 dB transition at the *upsampled* rate.  The former design needed
    509 taps and could not keep up with real time on one i5-9500 core.  Split
    the job instead:

    1. an elliptic IIR at the input rate removes everything that would alias
       above the output Nyquist frequency;
    2. a short FIR at the upsampled rate only has to reject the distant images
       introduced by zero insertion.

    The two filters retain the 0.4 * output-rate passband and at least 80 dB
    stopband target while reducing the 10 -> 4 MS/s polyphase FIR from 509 to
    fewer than twenty coefficients.
    """
    if input_rate <= 0 or output_rate <= 0 or output_rate >= input_rate:
        raise ValueError("fractional decimator requires 0 < output_rate < input_rate")
    ratio = Fraction(output_rate, input_rate)
    up, down = ratio.numerator, ratio.denominator
    if up <= 1:
        raise ValueError("fractional decimator requires a non-integer ratio")

    passband_ripple_db = 0.05
    stopband_attenuation_db = 82.0
    passband = 0.8 * output_rate / input_rate
    stopband = output_rate / input_rate
    order, critical = signal.ellipord(
        passband,
        stopband,
        passband_ripple_db,
        stopband_attenuation_db,
    )
    prefilter_sos = signal.ellip(
        order,
        passband_ripple_db,
        stopband_attenuation_db,
        critical,
        btype="low",
        output="sos",
    )

    design_rate = input_rate * up
    useful_edge_hz = 0.40 * output_rate
    # The closest zero-insertion image begins at input_rate - output_rate / 2.
    # The IIR has already removed the original spectrum above output_rate / 2,
    # so this wide transition is sufficient for the interpolation FIR.
    image_edge_hz = input_rate - 0.50 * output_rate
    transition_width = (image_edge_hz - useful_edge_hz) / (design_rate / 2.0)
    if not 0.0 < transition_width < 1.0:
        raise ValueError("fractional interpolation transition is invalid")
    fir_order, beta = signal.kaiserord(85.0, transition_width)
    fir_taps = max(7, int(fir_order))
    if fir_taps % 2 == 0:
        fir_taps += 1
    cutoff_hz = (useful_edge_hz + image_edge_hz) / 2.0
    interpolation_taps = signal.firwin(
        fir_taps,
        cutoff_hz / (design_rate / 2.0),
        window=("kaiser", beta),
    )
    interpolation_taps *= up

    numerator, denominator = signal.sos2tf(prefilter_sos)
    with np.errstate(all="ignore"):
        _, iir_delay = signal.group_delay((numerator, denominator), w=[0.0])
    iir_delay_samples = max(0.0, float(iir_delay[0]))
    fir_delay_input_samples = ((fir_taps - 1) / 2.0) / up

    # Measure the short FIR rather than merely reporting the Kaiser target.
    frequencies, response = signal.freqz(interpolation_taps, worN=131072)
    frequency_hz = frequencies / math.pi * (design_rate / 2.0)
    normalized_response = np.abs(response) / up
    fir_passband = normalized_response[frequency_hz <= useful_edge_hz]
    fir_stopband = normalized_response[frequency_hz >= image_edge_hz]
    fir_passband_db = 20.0 * np.log10(np.maximum(fir_passband, 1e-300))
    fir_ripple_db = float(np.max(fir_passband_db) - np.min(fir_passband_db))
    fir_attenuation_db = float(
        -20.0 * np.log10(max(float(np.max(fir_stopband)), 1e-300))
    )

    total_delay_samples = iir_delay_samples + fir_delay_input_samples
    characterization = FilterCharacterization(
        taps=(order + 1) + fir_taps,
        up=up,
        down=down,
        group_delay_input_samples=total_delay_samples,
        group_delay_seconds=total_delay_samples / input_rate,
        passband_ripple_db=passband_ripple_db + fir_ripple_db,
        stopband_attenuation_db=min(stopband_attenuation_db, fir_attenuation_db),
    )
    return prefilter_sos, interpolation_taps, characterization


class StreamingRationalResampler:
    """FIR rationnel causal, réalisé avec upfirdn et historique inter-blocs."""

    def __init__(self, input_rate: int, output_rate: int, *, _allow_multistage: bool = True):
        self.input_rate = int(input_rate)
        self.output_rate = int(output_rate)
        ratio = Fraction(output_rate, input_rate)
        self.up = ratio.numerator
        self.down = ratio.denominator
        self._integer_stage: StreamingIntegerDecimator | None = None
        self._final_stage: StreamingRationalResampler | None = None
        self._prefilter_sos: np.ndarray | None = None

        if self.up == 1 and self.down > 1:
            self._integer_stage = StreamingIntegerDecimator(input_rate, self.down)
            self.taps = np.empty(0, dtype=np.float64)
            self.characterization = self._integer_stage.characterization
        else:
            prefactor = _largest_integer_prefactor(input_rate, output_rate, self.down) if _allow_multistage else 1
            if prefactor > 1:
                intermediate_rate = input_rate // prefactor
                self._integer_stage = StreamingIntegerDecimator(input_rate, prefactor)
                self._final_stage = StreamingRationalResampler(
                    intermediate_rate,
                    output_rate,
                    _allow_multistage=False,
                )
                final = self._final_stage.characterization
                integer = self._integer_stage.characterization
                delay_seconds = integer.group_delay_seconds + final.group_delay_seconds
                self.taps = self._final_stage.taps
                self.characterization = FilterCharacterization(
                    taps=integer.taps + final.taps,
                    up=self.up,
                    down=self.down,
                    group_delay_input_samples=delay_seconds * input_rate,
                    group_delay_seconds=delay_seconds,
                    passband_ripple_db=integer.passband_ripple_db + final.passband_ripple_db,
                    stopband_attenuation_db=min(integer.stopband_attenuation_db, final.stopband_attenuation_db),
                )
            else:
                self._prefilter_sos, self.taps, self.characterization = (
                    design_fractional_decimator_filters(input_rate, output_rate)
                )
        if self._integer_stage is not None:
            self._history_inputs = 0
            self._history_capacity = 0
        else:
            self._history_inputs = int(math.ceil((len(self.taps) - 1) / self.up))
            self._history_capacity = self._history_inputs + self.down
        self.reset()

    def reset(self) -> None:
        if self._integer_stage is not None:
            self._integer_stage.reset()
        if self._final_stage is not None:
            self._final_stage.reset()
        if self._prefilter_sos is not None:
            self._prefilter_state = np.zeros(
                (len(self._prefilter_sos), 2),
                dtype=np.complex128,
            )
        self._history = np.empty(0, dtype=np.complex64)
        self._input_seen = 0
        self._next_output_index = 0

    def process(self, values: np.ndarray) -> np.ndarray:
        data = np.asarray(values, dtype=np.complex64)
        if not len(data):
            return np.empty(0, dtype=np.complex64)
        if self._integer_stage is not None:
            decimated = self._integer_stage.process(data)
            if self._final_stage is not None:
                return self._final_stage.process(decimated)
            return decimated
        if self._prefilter_sos is not None:
            data, self._prefilter_state = signal.sosfilt(
                self._prefilter_sos,
                data,
                zi=self._prefilter_state,
            )
            data = data.astype(np.complex64, copy=False)
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


def _largest_integer_prefactor(input_rate: int, output_rate: int, reduced_down: int) -> int:
    """Return a useful exact decimation stage before a rational conversion."""
    limit = input_rate // output_rate
    if limit < 2:
        return 1
    candidates = {1}
    for divisor in range(2, math.isqrt(reduced_down) + 1):
        if reduced_down % divisor:
            continue
        if divisor <= limit and input_rate % divisor == 0:
            candidates.add(divisor)
        paired = reduced_down // divisor
        if paired <= limit and input_rate % paired == 0:
            candidates.add(paired)
    return max(candidates)


@lru_cache(maxsize=32)
def design_integer_decimator_filter(input_rate: int, factor: int) -> tuple[np.ndarray, FilterCharacterization]:
    """Design a compact causal elliptic anti-alias filter for integer decimation."""
    if input_rate <= 0 or factor < 2 or input_rate % factor:
        raise ValueError("integer decimator requires an exact factor >= 2")
    passband = 0.8 / factor
    stopband = 1.0 / factor
    ripple_db = 0.1
    attenuation_db = 80.0
    order, critical = signal.ellipord(passband, stopband, ripple_db, attenuation_db)
    sos = signal.ellip(order, ripple_db, attenuation_db, critical, btype="low", output="sos")
    numerator, denominator = signal.sos2tf(sos)
    with np.errstate(all="ignore"):
        _, delay = signal.group_delay((numerator, denominator), w=[0.0])
    delay_samples = max(0.0, float(delay[0]))
    characterization = FilterCharacterization(
        taps=order + 1,
        up=1,
        down=factor,
        group_delay_input_samples=delay_samples,
        group_delay_seconds=delay_samples / input_rate,
        passband_ripple_db=ripple_db,
        stopband_attenuation_db=attenuation_db,
    )
    return sos, characterization


class StreamingIntegerDecimator:
    """Fast streaming IIR decimator with phase preserved across input blocks."""

    def __init__(self, input_rate: int, factor: int):
        self.input_rate = int(input_rate)
        self.factor = int(factor)
        self.sos, self.characterization = design_integer_decimator_filter(self.input_rate, self.factor)
        self.reset()

    def reset(self) -> None:
        self._state = np.zeros((len(self.sos), 2), dtype=np.complex128)
        self._input_seen = 0

    def process(self, values: np.ndarray) -> np.ndarray:
        data = np.asarray(values, dtype=np.complex64)
        if not len(data):
            return np.empty(0, dtype=np.complex64)
        filtered, self._state = signal.sosfilt(self.sos, data, zi=self._state)
        first = (-self._input_seen) % self.factor
        self._input_seen += len(data)
        return filtered[first::self.factor].astype(np.complex64, copy=False)


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
            # Profile rings persist while the source is stopped, replaced or
            # recovered.  Their publication sequence must therefore stay
            # monotone just like the master ring; first_sample_index remains
            # epoch-local and the DSP state is reset below.
            self.first_sample_index = 0
            if self.resampler:
                self.resampler.reset()
        try:
            if self.resampler is None and block.sample_format is self.output_format:
                # The full-rate CS16 operator profile is a routing operation,
                # not a DSP operation. Reuse the immutable payload instead of
                # converting every sample to complex64 and back.
                output_count = block.sample_count
                payload = block.payload
            else:
                values = payload_to_complex(block.payload, block.sample_format)
                output = values if self.resampler is None else self.resampler.process(values)
                if not len(output):
                    return None
                output_count = len(output)
                payload = memoryview(complex_to_payload(output, self.output_format))
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
            sample_count=output_count,
            sample_rate_sps=self.output_rate,
            center_frequency_hz=block.center_frequency_hz,
            config_revision=block.config_revision,
            sample_format=self.output_format,
            timestamp_ns=timestamp,
            time_domain=block.time_domain,
            timestamp_origin=origin,
            discontinuity=discontinuity,
            lost_samples=block.lost_samples,
            payload=payload,
        )
        self.sequence += 1
        self.first_sample_index += output_count
        self.blocks_processed += 1
        self.samples_produced += output_count
        return result
