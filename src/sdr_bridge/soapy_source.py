from __future__ import annotations

import hashlib
import json
import logging
import os
import queue
import threading
import time
from dataclasses import replace
from typing import Any

import numpy as np

from .model import (
    choose_auto_wire_format,
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

    # Several native Soapy modules keep transport state on the device object,
    # not only on the stream handle.  Reopening the device for a stream
    # topology change is slower, but prevents stale UHD/USB state from being
    # reused after a live sample-rate or WIRE-format change.
    reopen_on_stream_reconfigure = True

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
        self._resolved_wire_format: str | None = None
        self._read_calls = 0
        self._short_reads = 0
        self._minimum_read_samples = 0
        self._maximum_read_samples = 0
        self._rx_overflows = 0
        self._stream_mtu_samples = 0
        self._handoff_pool_blocks = 256
        self._handoff_pool_misses = 0
        self._device_args_effective: dict[str, str] = {}
        self._stream_args_effective: dict[str, str] = {}
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

    def diagnostics(self) -> dict[str, Any]:
        return {
            "wire_format_effective": self._resolved_wire_format,
            "host_stream_format": self._stream_format,
            "read_calls": self._read_calls,
            "short_reads": self._short_reads,
            "minimum_read_samples": self._minimum_read_samples,
            "maximum_read_samples": self._maximum_read_samples,
            "published_block_samples": self.block_samples,
            "rx_overflows": self._rx_overflows,
            "stream_mtu_samples": self._stream_mtu_samples,
            "handoff_pool_blocks": self._handoff_pool_blocks,
            "handoff_pool_misses": self._handoff_pool_misses,
            "device_args_effective": dict(self._device_args_effective),
            "stream_args_effective": dict(self._stream_args_effective),
        }

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
            device_args = dict(raw)
            # SoapyUHD exposes num_recv_frames as a generic receive-transport
            # parameter. UHD's USB devices otherwise default to only 16
            # simultaneous transfers, which is too little scheduling headroom
            # for a Windows GUI/DSP application at high sample rates. Apply
            # the tuning to the UHD backend, not to a receiver model; an
            # explicit discovery/configuration value always wins.
            if str(device_args.get("driver", self.driver or "")).lower() == "uhd":
                device_args.setdefault("num_recv_frames", "1024")
            self._device_args_effective = {
                str(key): str(value) for key, value in device_args.items()
            }
            self._device = self._api().Device(device_args)
            self._descriptor = self._descriptor_from_raw(raw)

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
            stream_args_info = self._optional_call(
                device, "getStreamArgsInfo", api.SOAPY_SDR_RX, 0, default=()
            )
            wire_formats: tuple[str, ...] = ()
            wire_format_default: str | None = None
            for info in stream_args_info:
                key = str(getattr(info, "key", ""))
                if key.upper() != "WIRE":
                    continue
                wire_formats = tuple(
                    dict.fromkeys(
                        str(value) for value in (getattr(info, "options", ()) or ()) if str(value)
                    )
                )
                raw_default = str(getattr(info, "value", "") or "")
                wire_format_default = raw_default if raw_default in wire_formats else None
                break
            agc_available = bool(self._optional_call(
                device, "hasGainMode", api.SOAPY_SDR_RX, 0, default=False
            ))
            return DeviceCapabilities(
                device_id, frequency_ranges, rates, bandwidths, antennas, gains,
                agc_available, (SampleFormat.CS16,), 1, rate_ranges,
                bandwidth_ranges, gain_values, gain_steps,
                wire_formats, wire_format_default,
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

    @staticmethod
    def _closest_supported_value(
        requested: int,
        discrete: tuple[int, ...],
        ranges: tuple[tuple[float, float, float], ...],
    ) -> int:
        """Choose only values reported by the driver; never use a model table."""
        if discrete:
            return min(discrete, key=lambda value: (abs(int(value) - requested), int(value)))
        if not ranges:
            return requested
        candidates: list[int] = []
        for low, high, step in ranges:
            low_i, high_i = int(round(low)), int(round(high))
            if low_i <= requested <= high_i:
                if step > 0:
                    snapped = low_i + round((requested - low_i) / step) * int(round(step))
                    return max(low_i, min(high_i, int(snapped)))
                return requested
            candidates.extend((low_i, high_i))
        return min(candidates, key=lambda value: (abs(value - requested), value))

    def _normalise_request(self, request: RadioConfig, capabilities: DeviceCapabilities) -> RadioConfig:
        wire_format = request.wire_format
        if wire_format is not None:
            match = next(
                (value for value in capabilities.wire_formats if value.lower() == wire_format.lower()),
                None,
            )
            if match is None:
                raise ValueError(f"unsupported IQ transport format: {wire_format}")
            wire_format = match
        return replace(
            request,
            sample_rate_sps=self._closest_supported_value(
                request.sample_rate_sps,
                capabilities.sample_rates_sps,
                capabilities.sample_rate_ranges_sps,
            ),
            bandwidth_hz=self._closest_supported_value(
                request.bandwidth_hz,
                capabilities.bandwidths_hz,
                capabilities.bandwidth_ranges_hz,
            ),
            wire_format=wire_format,
        )

    def _set_requested(self, config: RadioConfig, capabilities: DeviceCapabilities) -> None:
        api, dev = self._api(), self._device
        if dev is None:
            raise RuntimeError("Soapy source is not open")
        available_gains = set(str(value) for value in self._optional_call(
            dev, "listGains", api.SOAPY_SDR_RX, 0, default=()
        ))
        dev.setSampleRate(api.SOAPY_SDR_RX, 0, float(config.sample_rate_sps))
        dev.setFrequency(api.SOAPY_SDR_RX, 0, float(config.center_frequency_hz))
        if (
            capabilities.bandwidths_hz or capabilities.bandwidth_ranges_hz
        ) and hasattr(dev, "setBandwidth"):
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
        if self._device is None or self._descriptor is None:
            raise RuntimeError("Soapy source is not open")
        capabilities = self._capabilities_unlocked(self._descriptor.device_id)
        request = self._normalise_request(request, capabilities)
        request.validate()
        maximum_rate = max(
            (*capabilities.sample_rates_sps, *(int(item[1]) for item in capabilities.sample_rate_ranges_sps)),
            default=0,
        )
        self._resolved_wire_format = request.wire_format or choose_auto_wire_format(
            capabilities.wire_formats,
            capabilities.wire_format_default,
            request.sample_rate_sps,
            maximum_rate,
        )
        self._set_requested(request, capabilities)
        dev, api = self._device, self._api()
        frequency = int(round(self._optional_call(
            dev, "getFrequency", api.SOAPY_SDR_RX, 0, default=request.center_frequency_hz
        )))
        rate = int(round(self._optional_call(
            dev, "getSampleRate", api.SOAPY_SDR_RX, 0, default=request.sample_rate_sps
        )))
        bandwidth = int(round(self._optional_call(
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
            wire_format=request.wire_format,
        )
        return self._config

    def apply_config(self, config: RadioConfig) -> None:
        self.configure(config)

    def start(self, on_block: BlockCallback, on_error: ErrorCallback | None = None) -> None:
        with self._control_lock:
            if self._device is None:
                raise RuntimeError("Soapy source is not open")
            if self._thread and self._thread.is_alive():
                raise RuntimeError("source already started")
            api = self._api()
            self._on_block, self._on_error = on_block, on_error
            stream_args = {"WIRE": self._resolved_wire_format} if self._resolved_wire_format else None
            self._stream_args_effective = {
                str(key): str(value) for key, value in (stream_args or {}).items()
            }
            preferred_formats: list[str] = []
            if str(self._resolved_wire_format or "").lower() == "sc8":
                # Keep the high-rate path eight-bit until a complete bridge
                # block has been collected.  Asking SoapyUHD for CS16 here
                # forced a per-fragment SC8 -> CS16 conversion and doubled the
                # host-side copy traffic before SDRbridge could aggregate it.
                preferred_formats.append(getattr(api, "SOAPY_SDR_CS8", "CS8"))
            preferred_formats.extend((
                getattr(api, "SOAPY_SDR_CS16", "CS16"),
                getattr(api, "SOAPY_SDR_CF32", "CF32"),
            ))
            setup_errors: list[tuple[str, str]] = []
            for host_format in dict.fromkeys(preferred_formats):
                try:
                    self._stream = self._device.setupStream(
                        api.SOAPY_SDR_RX, host_format, args=stream_args
                    )
                    self._stream_format = str(host_format).upper()
                    break
                except Exception as exc:
                    setup_errors.append((str(host_format), str(exc)))
            if self._stream is None:
                raise RuntimeError(f"Soapy stream setup failed: {setup_errors}")
            if setup_errors:
                logger.info(
                    "preferred Soapy host format unavailable; using fallback",
                    extra={
                        "code": "SOAPY_HOST_FORMAT_FALLBACK",
                        "details": {
                            "selected": self._stream_format,
                            "failed": setup_errors,
                        },
                    },
                )
            try:
                self._device.activateStream(self._stream)
            except BaseException:
                stream, self._stream = self._stream, None
                if stream is not None:
                    self._device.closeStream(stream)
                raise
            self._stream_mtu_samples = int(self._optional_call(
                self._device, "getStreamMTU", self._stream, default=0
            ) or 0)
            self._stop.clear()
            self._first_sample = 0
            self._read_calls = 0
            self._short_reads = 0
            self._minimum_read_samples = 0
            self._maximum_read_samples = 0
            self._rx_overflows = 0
            self._handoff_pool_misses = 0
            self._thread = threading.Thread(target=self._run, name="soapy-rx", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        with self._control_lock:
            thread = self._thread
            if thread and thread is not threading.current_thread():
                thread.join(timeout=2.0)
                if thread.is_alive():
                    raise RuntimeError("Soapy RX thread did not stop")
            self._thread = None
            stream, self._stream = self._stream, None
            if self._device is not None and stream is not None:
                try:
                    self._device.deactivateStream(stream)
                finally:
                    self._device.closeStream(stream)

    def close(self) -> None:
        with self._control_lock:
            self.stop()
            device, self._device = self._device, None
            self._descriptor = None
            close = getattr(device, "close", None)
            if callable(close):
                close()

    @staticmethod
    def _raise_rx_thread_priority() -> None:
        """Reduce scheduling jitter on high-rate USB streams on Windows."""
        if os.name != "nt":
            return
        try:
            import ctypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.GetCurrentThread.restype = ctypes.c_void_p
            kernel32.SetThreadPriority.argtypes = (ctypes.c_void_p, ctypes.c_int)
            # THREAD_PRIORITY_HIGHEST within the normal process class. This
            # remains below time-critical priority and leaves the dispatcher,
            # DSP workers and GUI schedulable.
            kernel32.SetThreadPriority(kernel32.GetCurrentThread(), 2)
        except Exception:
            logger.debug("could not raise Soapy RX thread priority", exc_info=True)

    def _run(self) -> None:
        self._raise_rx_thread_priority()
        api = self._api()
        direct_cs16 = self._stream_format == "CS16"
        direct_cs8 = self._stream_format == "CS8"
        overflow_code = getattr(api, "SOAPY_SDR_OVERFLOW", -4)
        pending_source_loss = False
        next_overflow_log_at = 0.0
        if direct_cs8:
            buffer = np.empty((self.block_samples, 2), dtype="i1")
        elif direct_cs16:
            buffer = np.empty((self.block_samples, 2), dtype="<i2")
        else:
            buffer = np.empty(self.block_samples, dtype=np.complex64)
        # UHD and some USB backends may return transport-sized fragments far
        # smaller than the requested application block. Publishing every one
        # separately multiplies Python queue/ring/DSP overhead by thousands at
        # high rates. Coalesce them into the configured bridge block size.
        handoff_pool: queue.SimpleQueue[np.ndarray] | None = None
        handoff_return = None
        if direct_cs8:
            # Pre-allocate raw SC8 handoff blocks. Ownership is transferred to
            # the bridge until the dispatcher has widened the block to CS16,
            # so the UHD read thread no longer performs a 64 KiB bytes copy on
            # every 32768-sample block at 16 MS/s.
            handoff_pool = queue.SimpleQueue()
            for _ in range(self._handoff_pool_blocks):
                handoff_pool.put(np.empty((self.block_samples, 2), dtype="i1"))
            handoff_return = handoff_pool.put
            aggregate = handoff_pool.get()
        else:
            aggregate = np.empty((self.block_samples, 2), dtype="<i2")
        aggregate_count = 0
        aggregate_first_sample = 0
        aggregate_timestamp = 0
        aggregate_time_domain = TimeDomain.HOST_MONOTONIC
        aggregate_origin = TimestampOrigin.HOST_OBSERVATION
        stream_sample_index = 0
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
                    self._rx_overflows += 1
                    aggregate_count = 0
                    stream_sample_index = 0
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
                self._read_calls += 1
                if count < self.block_samples:
                    self._short_reads += 1
                self._minimum_read_samples = count if not self._minimum_read_samples else min(
                    self._minimum_read_samples, count
                )
                self._maximum_read_samples = max(self._maximum_read_samples, count)
                if direct_cs16 or direct_cs8:
                    values = buffer[:count]
                else:
                    samples = np.clip(buffer[:count].view(np.float32), -1.0, 0.9999695)
                    values = np.rint(samples * 32768.0).astype("<i2", copy=False).reshape(count, 2)
                timestamp = int(result.timeNs) if getattr(result, "timeNs", 0) else time.monotonic_ns()
                time_domain = TimeDomain.DEVICE_RELATIVE if getattr(result, "timeNs", 0) else TimeDomain.HOST_MONOTONIC
                origin = TimestampOrigin.HARDWARE if getattr(result, "timeNs", 0) else TimestampOrigin.HOST_OBSERVATION
                consumed = 0
                while consumed < count:
                    if aggregate_count == 0:
                        aggregate_first_sample = stream_sample_index + consumed
                        aggregate_timestamp = timestamp + round(
                            consumed * 1_000_000_000 / max(1, self._config.sample_rate_sps)
                        )
                        aggregate_time_domain = time_domain
                        aggregate_origin = origin
                    amount = min(self.block_samples - aggregate_count, count - consumed)
                    aggregate[aggregate_count:aggregate_count + amount] = values[consumed:consumed + amount]
                    aggregate_count += amount
                    consumed += amount
                    if aggregate_count != self.block_samples:
                        continue
                    discontinuity = Discontinuity.SOURCE_LOSS if pending_source_loss else Discontinuity.NONE
                    lost_samples = None if pending_source_loss else 0
                    completed = aggregate
                    self._on_block(SourceChunk(
                        memoryview(completed).cast("B"), aggregate_count, aggregate_first_sample,
                        aggregate_timestamp, aggregate_time_domain, aggregate_origin,
                        discontinuity, lost_samples,
                        "CS8" if direct_cs8 else "CS16",
                        handoff_return if direct_cs8 else None,
                        completed if direct_cs8 else None,
                    ))
                    pending_source_loss = False
                    aggregate_count = 0
                    if direct_cs8:
                        try:
                            aggregate = handoff_pool.get_nowait()
                        except queue.Empty:
                            # This is a safety fallback only: the bridge queue
                            # is bounded to the same order and normally returns
                            # a buffer long before the pool is exhausted.
                            self._handoff_pool_misses += 1
                            aggregate = np.empty((self.block_samples, 2), dtype="i1")
                stream_sample_index += count
                self._first_sample = stream_sample_index
        except BaseException as exc:
            if self._on_error and not self._stop.is_set():
                self._on_error(exc)


SoapySDRplaySource = SoapySource
