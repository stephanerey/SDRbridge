from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import replace
from typing import Any

import numpy as np

from .model import (
    DeviceCapabilities,
    DeviceDescriptor,
    Discontinuity,
    RadioConfig,
    SampleFormat,
    TimeDomain,
    TimestampOrigin,
)
from .source import BlockCallback, ErrorCallback, IQSource, SourceChunk
from .soapy_runtime import load_soapy_api


logger = logging.getLogger(__name__)


class SoapySource(IQSource):
    """Backend Soapy générique RX ; aucun appareil n'est ouvert à l'import."""

    NON_SDR_DRIVERS = frozenset({"audio"})
    DRIVER_PRIORITY = {
        "sdrplay": 10,
        "uhd": 20,
        "rtlsdr": 30,
        "airspy": 40,
        "airspyhf": 41,
        "hackrf": 50,
        "lime": 60,
        "plutosdr": 61,
        "miri": 90,
    }
    B100_CS16_MAX_RATE_SPS = 8_000_000

    def __init__(self, block_samples: int = 4096, driver: str | None = None, *, api: Any | None = None):
        self.block_samples = int(block_samples)
        self.driver = driver
        self._api_override = api
        self._config = RadioConfig()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._device = None
        self._stream = None
        self._stream_format = "CF32"
        self._descriptor: DeviceDescriptor | None = None
        self._on_block: BlockCallback | None = None
        self._on_error: ErrorCallback | None = None
        self._first_sample = 0
        self._control_lock = threading.RLock()
        self._last_raw_devices: list[dict[str, str]] = []
        self._active_raw_device: dict[str, str] = {}
        self._uhd_b100 = False

    @property
    def name(self) -> str:
        model = self._descriptor.model if self._descriptor else "non ouvert"
        return f"SoapySDR — {model}"

    def _api(self):
        if self._api_override is not None:
            return self._api_override
        self._api_override = load_soapy_api()
        return self._api_override

    def _query(self) -> list[dict[str, str]]:
        with self._control_lock:
            args = {"driver": self.driver} if self.driver else {}
            devices = [
                dict(item) for item in self._api().Device_enumerate(args)
                if str(item.get("driver", self.driver or "unknown")).lower() not in self.NON_SDR_DRIVERS
            ]
            devices = sorted(
                devices,
                key=lambda item: (
                    self.DRIVER_PRIORITY.get(str(item.get("driver", "unknown")).lower(), 70),
                    str(item.get("label", "")),
                    str(item.get("serial") or item.get("device_id") or ""),
                ),
            )
            self._last_raw_devices = devices
            return list(devices)

    def _descriptor_from_raw(self, raw: dict[str, str], index: int = 0) -> DeviceDescriptor:
        serial = raw.get("serial") or raw.get("device_id")
        driver = raw.get("driver", self.driver or "unknown").lower()
        label = raw.get("label") or raw.get("hardware") or raw.get("product") or driver
        # Many Soapy modules (RTL-SDR, UHD network discovery, remote, etc.) do
        # not expose a field literally named ``serial``.  Derive a stable key
        # from their discovery arguments instead of tying profiles to the
        # current enumeration order.  The label is intentionally excluded: it
        # is presentation text and some modules localise or decorate it.
        identity_args = {
            str(key): str(value)
            for key, value in raw.items()
            if str(key).lower() not in {"driver", "label"}
        }
        fingerprint = hashlib.sha256(
            json.dumps(identity_args, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:16]
        stable = serial or (fingerprint if identity_args else f"enumeration-{index}")
        return DeviceDescriptor(f"soapy:{driver}:{stable}", f"soapy/{driver}", label, serial=serial)

    def enumerate(self) -> list[DeviceDescriptor]:
        return [self._descriptor_from_raw(raw, index) for index, raw in enumerate(self._query())]

    def _raw_for_id(self, device_id: str) -> dict[str, str]:
        with self._control_lock:
            raw_devices = self._last_raw_devices or self._query()
            for index, raw in enumerate(raw_devices):
                if self._descriptor_from_raw(raw, index).device_id == device_id:
                    return dict(raw)
        raise KeyError(device_id)

    def open(self, device_id: str) -> None:
        # Device enumeration is a native global operation in several Soapy
        # modules (notably SDRplay).  Re-enumerating three times while opening
        # the already discovered device can race module teardown and has been
        # observed to raise a Windows access violation.  Reuse the discovery
        # record and claim the device exactly once.
        with self._control_lock:
            raw = self._raw_for_id(device_id)
            self._device = self._api().Device(raw)
            self._descriptor = self._descriptor_from_raw(raw)
            self._active_raw_device = dict(raw)
            self._uhd_b100 = self._is_uhd_b100(raw)

    def capabilities(self, device_id: str) -> DeviceCapabilities:
        with self._control_lock:
            return self._capabilities_unlocked(device_id)

    def _capabilities_unlocked(self, device_id: str) -> DeviceCapabilities:
        temporary = self._device is None or self._descriptor is None or self._descriptor.device_id != device_id
        raw = self._raw_for_id(device_id)
        device = self._api().Device(raw) if temporary else self._device
        api = self._api()
        try:
            rate_ranges = self._read_ranges(device, "getSampleRateRange", api)
            rates = tuple(sorted({
                int(round(value)) for value in self._optional_call(
                    device, "listSampleRates", api.SOAPY_SDR_RX, 0, default=()
                ) if float(value) > 0
            }))
            if not rates:
                rates = self._values_from_ranges(rate_ranges, self._config.sample_rate_sps)
            if not rates:
                rates = (self._config.sample_rate_sps,)
            antennas = tuple(str(value) for value in self._optional_call(
                device, "listAntennas", api.SOAPY_SDR_RX, 0, default=()
            ))
            gains: dict[str, tuple[float, float]] = {}
            gain_values: dict[str, float] = {}
            gain_steps: dict[str, float] = {}
            gain_names = tuple(str(value) for value in self._optional_call(
                device, "listGains", api.SOAPY_SDR_RX, 0, default=()
            ))
            is_uhd_b100 = self._is_uhd_b100(raw, gain_names)
            if is_uhd_b100:
                # UHD exposes rates that are usable only with 8-bit wire
                # samples. SDRbridge intentionally receives CS16, for which
                # the USB 2.0 B100 limit is 8 MS/s.
                rates = tuple(value for value in rates if value <= self.B100_CS16_MAX_RATE_SPS)
                if not rates:
                    rates = (min(self._config.sample_rate_sps, self.B100_CS16_MAX_RATE_SPS),)
                rate_ranges = tuple(
                    (low, min(high, float(self.B100_CS16_MAX_RATE_SPS)), step)
                    for low, high, step in rate_ranges
                    if low <= self.B100_CS16_MAX_RATE_SPS
                )
                if not temporary:
                    self._uhd_b100 = True
            for name in gain_names:
                value_range = self._optional_call(
                    device, "getGainRange", api.SOAPY_SDR_RX, 0, name, default=None
                )
                if value_range is not None:
                    low, high, *step = value_range
                    gains[name] = (float(low), float(high))
                    gain_steps[name] = float(step[0]) if step and step[0] else 1.0
                value = self._optional_call(
                    device, "getGain", api.SOAPY_SDR_RX, 0, name, default=None
                )
                if value is not None:
                    gain_values[name] = float(value)
            raw_frequency_ranges = self._optional_call(
                device, "getFrequencyRanges", api.SOAPY_SDR_RX, 0, default=()
            )
            frequency_ranges = tuple(
                (int(round(low)), int(round(high)))
                for low, high, *_ in raw_frequency_ranges
                if float(high) >= float(low) and float(high) > 0
            )
            bandwidth_ranges = self._read_ranges(device, "getBandwidthRange", api)
            bandwidths = tuple(sorted({
                int(round(value)) for value in self._optional_call(
                    device, "listBandwidths", api.SOAPY_SDR_RX, 0, default=()
                ) if float(value) > 0
            }))
            if not bandwidths:
                bandwidths = self._values_from_ranges(bandwidth_ranges, self._config.bandwidth_hz)
            if is_uhd_b100:
                # On the B100, UHD reports the daughterboard RF frontend
                # bandwidth (often hundreds of MHz) as if it were a tunable
                # baseband filter. It is not the IQ span and must not be sent
                # back through setBandwidth().
                bandwidths = ()
                bandwidth_ranges = ()
            agc_available = bool(self._optional_call(
                device, "hasGainMode", api.SOAPY_SDR_RX, 0, default=False
            ))
            return DeviceCapabilities(
                device_id, frequency_ranges, rates, bandwidths, antennas, gains,
                agc_available, (SampleFormat.CS16,), 1, rate_ranges,
                bandwidth_ranges, gain_values, gain_steps,
            )
        finally:
            if temporary:
                close = getattr(device, "close", None)
                if callable(close):
                    close()

    @staticmethod
    def _optional_call(device: Any, method_name: str, *args: Any, default: Any = None) -> Any:
        """Call an optional Soapy capability without rejecting the device.

        Soapy modules legitimately omit controls such as bandwidth, antenna,
        AGC, or individual gain stages.  Discovery of one optional control
        must not make an otherwise valid RX device unusable.
        """
        method = getattr(device, method_name, None)
        if method is None:
            return default
        try:
            return method(*args)
        except (AttributeError, NotImplementedError, RuntimeError, TypeError, ValueError) as exc:
            logger.debug(
                "optional Soapy capability is unavailable",
                extra={"code": "SOAPY_OPTIONAL_CAPABILITY", "details": {"method": method_name, "error": str(exc)}},
            )
            return default

    @staticmethod
    def _is_uhd_b100(raw: dict[str, Any], gain_names=()) -> bool:
        """Recognize the legacy USB B100 without relying on its display label."""
        driver = str(raw.get("driver", "")).lower()
        if driver != "uhd":
            return False
        identity = " ".join(
            str(raw.get(key, "")).lower()
            for key in ("type", "product", "hardware", "name", "label")
        )
        return "b100" in identity or any(str(name).lower() == "adc-pga" for name in gain_names)

    @staticmethod
    def _read_ranges(device: Any, method_name: str, api: Any) -> tuple[tuple[float, float, float], ...]:
        values = SoapySource._optional_call(
            device, method_name, api.SOAPY_SDR_RX, 0, default=()
        )
        return tuple(
            (float(item[0]), float(item[1]), float(item[2]) if len(item) > 2 else 0.0)
            for item in values
            if len(item) >= 2 and float(item[1]) >= float(item[0])
        )

    @staticmethod
    def _values_from_ranges(ranges, current: int) -> tuple[int, ...]:
        """Expose discrete ranges exactly; bound continuous ranges without inventing steps."""
        values: set[int] = set()
        for low, high, step in ranges:
            low_i, high_i = int(round(low)), int(round(high))
            if low_i == high_i:
                values.add(low_i)
                continue
            step_i = int(round(step))
            count = ((high_i - low_i) // step_i + 1) if step_i > 0 else 0
            if 0 < count <= 64:
                values.update(range(low_i, high_i + 1, step_i))
            else:
                values.update((low_i, high_i))
                if low_i <= int(current) <= high_i:
                    values.add(int(current))
        return tuple(sorted(value for value in values if value > 0))

    def _set_requested(self, config: RadioConfig) -> None:
        api, dev = self._api(), self._device
        if dev is None:
            raise RuntimeError("Soapy source is not open")
        available_gains = set(str(value) for value in self._optional_call(
            dev, "listGains", api.SOAPY_SDR_RX, 0, default=()
        ))
        self._uhd_b100 = self._uhd_b100 or self._is_uhd_b100(
            self._active_raw_device, available_gains
        )
        dev.setSampleRate(api.SOAPY_SDR_RX, 0, float(config.sample_rate_sps))
        dev.setFrequency(api.SOAPY_SDR_RX, 0, float(config.center_frequency_hz))
        bandwidths = self._optional_call(dev, "listBandwidths", api.SOAPY_SDR_RX, 0, default=())
        bandwidth_ranges = self._read_ranges(dev, "getBandwidthRange", api)
        if not self._uhd_b100 and (bandwidths or bandwidth_ranges) and hasattr(dev, "setBandwidth"):
            dev.setBandwidth(api.SOAPY_SDR_RX, 0, float(config.bandwidth_hz))
        antennas = tuple(str(value) for value in self._optional_call(
            dev, "listAntennas", api.SOAPY_SDR_RX, 0, default=()
        ))
        if config.antenna and config.antenna in antennas:
            dev.setAntenna(api.SOAPY_SDR_RX, 0, config.antenna)
        gain_mode_available = bool(self._optional_call(
            dev, "hasGainMode", api.SOAPY_SDR_RX, 0, default=False
        ))
        if gain_mode_available:
            dev.setGainMode(api.SOAPY_SDR_RX, 0, bool(config.agc_enabled))
        if not config.agc_enabled:
            requested_gains = dict(config.gains)
            if "IFGR" in available_gains and "IFGR" not in requested_gains:
                requested_gains["IFGR"] = config.gain_reduction_db
            if "RFGR" in available_gains and "RFGR" not in requested_gains and "lna_state" in requested_gains:
                requested_gains["RFGR"] = requested_gains["lna_state"]
            for name, value in requested_gains.items():
                if name not in available_gains:
                    continue
                dev.setGain(api.SOAPY_SDR_RX, 0, name, float(value))

    def configure(self, request: RadioConfig) -> RadioConfig:
        with self._control_lock:
            return self._configure_unlocked(request)

    def _configure_unlocked(self, request: RadioConfig) -> RadioConfig:
        if not self._uhd_b100 and self._device is not None:
            api = self._api()
            gain_names = self._optional_call(
                self._device, "listGains", api.SOAPY_SDR_RX, 0, default=()
            )
            self._uhd_b100 = self._is_uhd_b100(self._active_raw_device, gain_names)
        if self._uhd_b100:
            if request.sample_rate_sps > self.B100_CS16_MAX_RATE_SPS:
                raise ValueError("USRP B100 CS16 sample rate must not exceed 8 MS/s")
            if not 1 <= request.bandwidth_hz <= 20_000_000:
                # Recover configurations produced by the previous build,
                # which copied UHD's 500 MHz frontend readback into the bridge
                # setting and consequently rejected every later update.
                request = replace(
                    request,
                    bandwidth_hz=min(request.sample_rate_sps, self.B100_CS16_MAX_RATE_SPS),
                )
        request.validate()
        self._set_requested(request)
        dev, api = self._device, self._api()
        frequency = int(round(self._optional_call(
            dev, "getFrequency", api.SOAPY_SDR_RX, 0, default=request.center_frequency_hz
        )))
        rate = int(round(self._optional_call(
            dev, "getSampleRate", api.SOAPY_SDR_RX, 0, default=request.sample_rate_sps
        )))
        bandwidth = request.bandwidth_hz if self._uhd_b100 else int(round(self._optional_call(
            dev, "getBandwidth", api.SOAPY_SDR_RX, 0, default=request.bandwidth_hz
        )))
        gain_names = tuple(str(value) for value in self._optional_call(
            dev, "listGains", api.SOAPY_SDR_RX, 0, default=()
        ))
        gains = {
            name: float(value)
            for name in gain_names
            if (value := self._optional_call(
                dev, "getGain", api.SOAPY_SDR_RX, 0, name, default=None
            )) is not None
        }
        agc = bool(self._optional_call(
            dev, "getGainMode", api.SOAPY_SDR_RX, 0, default=request.agc_enabled
        ))
        antenna = self._optional_call(
            dev, "getAntenna", api.SOAPY_SDR_RX, 0, default=request.antenna
        )
        self._config = RadioConfig(
            center_frequency_hz=frequency,
            sample_rate_sps=rate,
            bandwidth_hz=bandwidth,
            gain_reduction_db=int(round(gains.get("IFGR", request.gain_reduction_db))),
            agc_enabled=agc,
            antenna=antenna or request.antenna,
            gains=gains or request.gains,
            sample_format=SampleFormat.CS16,
            revision=request.revision,
        )
        return self._config

    def apply_config(self, config: RadioConfig) -> None:
        self.configure(config)

    def start(self, on_block: BlockCallback, on_error: ErrorCallback | None = None) -> None:
        if self._device is None:
            raise RuntimeError("Soapy source is not open")
        if self._thread and self._thread.is_alive():
            raise RuntimeError("source already started")
        api = self._api()
        self._on_block, self._on_error = on_block, on_error
        requested_cs16 = getattr(api, "SOAPY_SDR_CS16", "CS16")
        try:
            # Ask Soapy to perform the native/converter step in its compiled
            # stream path. Converting 8-10 MS/s CF32 to CS16 with NumPy in a
            # Python RX thread contended with the dispatcher and filled the
            # source queue even though the machine-wide CPU was not full.
            self._stream = self._device.setupStream(api.SOAPY_SDR_RX, requested_cs16)
            self._stream_format = "CS16"
        except Exception as exc:
            self._stream = self._device.setupStream(api.SOAPY_SDR_RX, api.SOAPY_SDR_CF32)
            self._stream_format = "CF32"
            logger.warning(
                "Soapy CS16 stream unavailable; falling back to Python CF32 conversion",
                extra={"code": "SOAPY_CF32_FALLBACK", "details": {"error": str(exc)}},
            )
        self._device.activateStream(self._stream)
        self._stop.clear()
        self._first_sample = 0
        self._thread = threading.Thread(target=self._run, name="soapy-rx", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=2.0)
            if self._thread.is_alive():
                raise RuntimeError("Soapy RX thread did not stop")
        if self._device is not None and self._stream is not None:
            try:
                self._device.deactivateStream(self._stream)
            finally:
                self._device.closeStream(self._stream)
        self._thread = None
        self._stream = None

    def close(self) -> None:
        self.stop()
        self._device = None
        self._descriptor = None
        self._active_raw_device = {}
        self._uhd_b100 = False

    def _run(self) -> None:
        api = self._api()
        direct_cs16 = self._stream_format == "CS16"
        overflow_code = getattr(api, "SOAPY_SDR_OVERFLOW", -4)
        pending_source_loss = False
        next_overflow_log_at = 0.0
        buffer = (
            np.empty((self.block_samples, 2), dtype="<i2")
            if direct_cs16
            else np.empty(self.block_samples, dtype=np.complex64)
        )
        try:
            while not self._stop.is_set():
                result = self._device.readStream(self._stream, [buffer], self.block_samples, timeoutUs=250_000)
                if result.ret == api.SOAPY_SDR_TIMEOUT:
                    continue
                if result.ret == overflow_code:
                    # Soapy uses OVERFLOW to report that samples were lost
                    # between two reads.  The stream itself remains usable;
                    # treating this as a fatal error unnecessarily stopped RX
                    # until the operator pressed Play again.  Mark the next
                    # published block as a continuity break so rings, DSP and
                    # recorders can reset safely while acquisition continues.
                    pending_source_loss = True
                    self._first_sample = 0
                    now = time.monotonic()
                    if now >= next_overflow_log_at:
                        next_overflow_log_at = now + 5.0
                        logger.warning(
                            "SoapySDR reported a recoverable RX overflow",
                            extra={"code": "SOAPY_RX_OVERFLOW"},
                        )
                    continue
                if result.ret < 0:
                    raise RuntimeError(f"SoapySDR readStream failed: {result.ret}")
                count = int(result.ret)
                if direct_cs16:
                    values = buffer[:count]
                else:
                    samples = np.clip(buffer[:count].view(np.float32), -1.0, 0.9999695)
                    values = np.rint(samples * 32768.0).astype("<i2", copy=False)
                timestamp = int(result.timeNs) if getattr(result, "timeNs", 0) else time.monotonic_ns()
                time_domain = TimeDomain.DEVICE_RELATIVE if getattr(result, "timeNs", 0) else TimeDomain.HOST_MONOTONIC
                origin = TimestampOrigin.HARDWARE if getattr(result, "timeNs", 0) else TimestampOrigin.HOST_OBSERVATION
                discontinuity = Discontinuity.SOURCE_LOSS if pending_source_loss else Discontinuity.NONE
                lost_samples = None if pending_source_loss else 0
                self._on_block(SourceChunk(
                    memoryview(values).cast("B"), count, self._first_sample,
                    timestamp, time_domain, origin, discontinuity, lost_samples,
                ))
                pending_source_loss = False
                self._first_sample += count
        except BaseException as exc:
            if self._on_error and not self._stop.is_set():
                self._on_error(exc)


SoapySDRplaySource = SoapySource
