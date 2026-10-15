from __future__ import annotations

import threading
import time
from typing import Any

import numpy as np

from .model import DeviceCapabilities, DeviceDescriptor, RadioConfig, SampleFormat, TimeDomain, TimestampOrigin
from .source import BlockCallback, ErrorCallback, IQSource, SourceChunk
from .soapy_runtime import load_soapy_api


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
        self._descriptor: DeviceDescriptor | None = None
        self._on_block: BlockCallback | None = None
        self._on_error: ErrorCallback | None = None
        self._first_sample = 0

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
        args = {"driver": self.driver} if self.driver else {}
        devices = [
            dict(item) for item in self._api().Device_enumerate(args)
            if str(item.get("driver", self.driver or "unknown")).lower() not in self.NON_SDR_DRIVERS
        ]
        return sorted(
            devices,
            key=lambda item: (
                self.DRIVER_PRIORITY.get(str(item.get("driver", "unknown")).lower(), 70),
                str(item.get("label", "")),
                str(item.get("serial") or item.get("device_id") or ""),
            ),
        )

    def enumerate(self) -> list[DeviceDescriptor]:
        result: list[DeviceDescriptor] = []
        for index, raw in enumerate(self._query()):
            serial = raw.get("serial") or raw.get("device_id")
            driver = raw.get("driver", self.driver or "unknown").lower()
            label = raw.get("label") or raw.get("hardware") or raw.get("product") or driver
            stable = serial or f"enumeration-{index}"
            result.append(DeviceDescriptor(f"soapy:{driver}:{stable}", f"soapy/{driver}", label, serial=serial))
        return result

    def _raw_for_id(self, device_id: str) -> dict[str, str]:
        descriptors = self.enumerate()
        raw_devices = self._query()
        for descriptor, raw in zip(descriptors, raw_devices):
            if descriptor.device_id == device_id:
                return raw
        raise KeyError(device_id)

    def open(self, device_id: str) -> None:
        raw = self._raw_for_id(device_id)
        self._device = self._api().Device(raw)
        self._descriptor = next(item for item in self.enumerate() if item.device_id == device_id)

    def capabilities(self, device_id: str) -> DeviceCapabilities:
        temporary = self._device is None or self._descriptor is None or self._descriptor.device_id != device_id
        device = self._api().Device(self._raw_for_id(device_id)) if temporary else self._device
        api = self._api()
        rates = tuple(sorted({int(round(value)) for value in device.listSampleRates(api.SOAPY_SDR_RX, 0)}))
        antennas = tuple(device.listAntennas(api.SOAPY_SDR_RX, 0))
        gains = {}
        for name in device.listGains(api.SOAPY_SDR_RX, 0):
            if hasattr(device, "getGainRange"):
                low, high, *_ = device.getGainRange(api.SOAPY_SDR_RX, 0, name)
                gains[name] = (float(low), float(high))
        frequency_ranges = ((1_000, 2_000_000_001),)
        if hasattr(device, "getFrequencyRanges"):
            frequency_ranges = tuple((int(low), int(high)) for low, high, *_ in device.getFrequencyRanges(api.SOAPY_SDR_RX, 0))
        bandwidths = rates
        if hasattr(device, "listBandwidths"):
            bandwidths = tuple(sorted({int(round(value)) for value in device.listBandwidths(api.SOAPY_SDR_RX, 0)}))
        return DeviceCapabilities(device_id, frequency_ranges, rates, bandwidths, antennas, gains, True, (SampleFormat.CS16,))

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
        dev.setGainMode(api.SOAPY_SDR_RX, 0, bool(config.agc_enabled))
        if not config.agc_enabled:
            for name, value in config.gains.items():
                dev.setGain(api.SOAPY_SDR_RX, 0, name, float(value))

    def configure(self, request: RadioConfig) -> RadioConfig:
        request.validate()
        self._set_requested(request)
        dev, api = self._device, self._api()
        frequency = int(round(dev.getFrequency(api.SOAPY_SDR_RX, 0))) if hasattr(dev, "getFrequency") else request.center_frequency_hz
        rate = int(round(dev.getSampleRate(api.SOAPY_SDR_RX, 0))) if hasattr(dev, "getSampleRate") else request.sample_rate_sps
        bandwidth = int(round(dev.getBandwidth(api.SOAPY_SDR_RX, 0))) if hasattr(dev, "getBandwidth") else request.bandwidth_hz
        self._config = RadioConfig(
            center_frequency_hz=frequency,
            sample_rate_sps=rate,
            bandwidth_hz=bandwidth,
            gain_reduction_db=request.gain_reduction_db,
            agc_enabled=request.agc_enabled,
            antenna=request.antenna,
            gains=request.gains,
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
        self._stream = self._device.setupStream(api.SOAPY_SDR_RX, api.SOAPY_SDR_CF32)
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
        cf32 = np.empty(self.block_samples, dtype=np.complex64)
        try:
            while not self._stop.is_set():
                result = self._device.readStream(self._stream, [cf32], self.block_samples, timeoutUs=250_000)
                if result.ret == api.SOAPY_SDR_TIMEOUT:
                    continue
                if result.ret < 0:
                    raise RuntimeError(f"SoapySDR readStream failed: {result.ret}")
                count = int(result.ret)
                samples = np.clip(cf32[:count].view(np.float32), -1.0, 0.9999695)
                values = np.rint(samples * 32768.0).astype("<i2", copy=False)
                timestamp = int(result.timeNs) if getattr(result, "timeNs", 0) else time.monotonic_ns()
                time_domain = TimeDomain.DEVICE_RELATIVE if getattr(result, "timeNs", 0) else TimeDomain.HOST_MONOTONIC
                origin = TimestampOrigin.HARDWARE if getattr(result, "timeNs", 0) else TimestampOrigin.HOST_OBSERVATION
                self._on_block(SourceChunk(memoryview(values).cast("B"), count, self._first_sample, timestamp, time_domain, origin))
                self._first_sample += count
        except BaseException as exc:
            if self._on_error and not self._stop.is_set():
                self._on_error(exc)


SoapySDRplaySource = SoapySource
