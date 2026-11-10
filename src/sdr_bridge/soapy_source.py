from __future__ import annotations

import logging
import threading
import time
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
        "miri": 90,
    }

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
        stable = serial or f"enumeration-{index}"
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

    def capabilities(self, device_id: str) -> DeviceCapabilities:
        with self._control_lock:
            return self._capabilities_unlocked(device_id)

    def _capabilities_unlocked(self, device_id: str) -> DeviceCapabilities:
        temporary = self._device is None or self._descriptor is None or self._descriptor.device_id != device_id
        device = self._api().Device(self._raw_for_id(device_id)) if temporary else self._device
        api = self._api()
        rate_ranges = self._read_ranges(device, "getSampleRateRange", api)
        rates = tuple(sorted({int(round(value)) for value in device.listSampleRates(api.SOAPY_SDR_RX, 0)}))
        if not rates:
            rates = self._values_from_ranges(rate_ranges, self._config.sample_rate_sps)
        antennas = tuple(device.listAntennas(api.SOAPY_SDR_RX, 0))
        gains = {}
        gain_values = {}
        gain_steps = {}
        for name in device.listGains(api.SOAPY_SDR_RX, 0):
            if hasattr(device, "getGainRange"):
                low, high, *step = device.getGainRange(api.SOAPY_SDR_RX, 0, name)
                gains[name] = (float(low), float(high))
                gain_steps[name] = float(step[0]) if step and step[0] else 1.0
            if hasattr(device, "getGain"):
                gain_values[name] = float(device.getGain(api.SOAPY_SDR_RX, 0, name))
        frequency_ranges = ((1_000, 2_000_000_001),)
        if hasattr(device, "getFrequencyRanges"):
            frequency_ranges = tuple((int(low), int(high)) for low, high, *_ in device.getFrequencyRanges(api.SOAPY_SDR_RX, 0))
        bandwidth_ranges = self._read_ranges(device, "getBandwidthRange", api)
        bandwidths = ()
        if hasattr(device, "listBandwidths"):
            bandwidths = tuple(sorted({int(round(value)) for value in device.listBandwidths(api.SOAPY_SDR_RX, 0)}))
        if not bandwidths:
            bandwidths = self._values_from_ranges(bandwidth_ranges, self._config.bandwidth_hz)
        if not bandwidths:
            bandwidths = rates
        agc_available = bool(device.hasGainMode(api.SOAPY_SDR_RX, 0)) if hasattr(device, "hasGainMode") else False
        result = DeviceCapabilities(
            device_id, frequency_ranges, rates, bandwidths, antennas, gains,
            agc_available, (SampleFormat.CS16,), 1, rate_ranges,
            bandwidth_ranges, gain_values, gain_steps,
        )
        if temporary:
            close = getattr(device, "close", None)
            if callable(close):
                close()
        return result

    @staticmethod
    def _read_ranges(device: Any, method_name: str, api: Any) -> tuple[tuple[float, float, float], ...]:
        method = getattr(device, method_name, None)
        if method is None:
            return ()
        return tuple(
            (float(item[0]), float(item[1]), float(item[2]) if len(item) > 2 else 0.0)
            for item in method(api.SOAPY_SDR_RX, 0)
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
        dev.setSampleRate(api.SOAPY_SDR_RX, 0, float(config.sample_rate_sps))
        dev.setFrequency(api.SOAPY_SDR_RX, 0, float(config.center_frequency_hz))
        if hasattr(dev, "setBandwidth"):
            dev.setBandwidth(api.SOAPY_SDR_RX, 0, float(config.bandwidth_hz))
        if config.antenna:
            dev.setAntenna(api.SOAPY_SDR_RX, 0, config.antenna)
        if hasattr(dev, "hasGainMode") and dev.hasGainMode(api.SOAPY_SDR_RX, 0):
            dev.setGainMode(api.SOAPY_SDR_RX, 0, bool(config.agc_enabled))
        if not config.agc_enabled:
            available_gains = set(dev.listGains(api.SOAPY_SDR_RX, 0))
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
        request.validate()
        self._set_requested(request)
        dev, api = self._device, self._api()
        frequency = int(round(dev.getFrequency(api.SOAPY_SDR_RX, 0))) if hasattr(dev, "getFrequency") else request.center_frequency_hz
        rate = int(round(dev.getSampleRate(api.SOAPY_SDR_RX, 0))) if hasattr(dev, "getSampleRate") else request.sample_rate_sps
        bandwidth = int(round(dev.getBandwidth(api.SOAPY_SDR_RX, 0))) if hasattr(dev, "getBandwidth") else request.bandwidth_hz
        gain_names = tuple(dev.listGains(api.SOAPY_SDR_RX, 0))
        gains = {
            name: float(dev.getGain(api.SOAPY_SDR_RX, 0, name))
            for name in gain_names
            if hasattr(dev, "getGain")
        }
        agc = bool(dev.getGainMode(api.SOAPY_SDR_RX, 0)) if hasattr(dev, "getGainMode") else request.agc_enabled
        antenna = dev.getAntenna(api.SOAPY_SDR_RX, 0) if hasattr(dev, "getAntenna") else request.antenna
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
