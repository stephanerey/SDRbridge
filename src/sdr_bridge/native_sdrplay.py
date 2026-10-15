from __future__ import annotations

import ctypes
import os
from pathlib import Path
import sys
import threading

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


class NativeSDRplaySource(IQSource):
    """Backend de secours SDRplay API 3.15, RX uniquement."""

    DEVICE_ID = "native-sdrplay:first-available"
    CALLBACK = ctypes.CFUNCTYPE(None, ctypes.POINTER(ctypes.c_int16), ctypes.c_uint32, ctypes.c_uint64, ctypes.c_void_p)

    def __init__(self, dll_path: str | None = None):
        self._dll_path = Path(dll_path) if dll_path else self._discover()
        self._dll: ctypes.CDLL | None = None
        self._api_dll: ctypes.CDLL | None = None
        self._callback: BlockCallback | None = None
        self._error_callback: ErrorCallback | None = None
        self._native_callback = self.CALLBACK(self._on_iq)
        self._config = RadioConfig()
        self._active = False
        self._opened = False
        self._reader_stop = threading.Event()
        self._reader_thread: threading.Thread | None = None
        self._error: BaseException | None = None
        self._dll_directory = None

    @property
    def name(self) -> str:
        return "SDRplay direct API 3.15 (secours)"

    @staticmethod
    def _discover() -> Path:
        candidates = []
        if hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS) / "native" / "sdrplay_bridge.dll")
        candidates.extend([
            Path(sys.executable).parent / "native" / "sdrplay_bridge.dll",
            Path(__file__).resolve().parents[2] / "native" / "build" / "sdrplay_bridge" / "Release" / "sdrplay_bridge.dll",
        ])
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise RuntimeError("sdrplay_bridge.dll not found; run native/build_native.ps1")

    def enumerate(self) -> list[DeviceDescriptor]:
        return [DeviceDescriptor(self.DEVICE_ID, "native_sdrplay", "First available SDRplay receiver", serial=None)]

    def capabilities(self, device_id: str) -> DeviceCapabilities:
        if device_id != self.DEVICE_ID:
            raise KeyError(device_id)
        # Ce backend cible explicitement la famille RSPdx. La validation de la
        # version réelle reste côté DLL avant toute écriture de paramètres.
        antennas = ("A", "B", "C")
        gains = {
            "gain_reduction_db": (20.0, 59.0),
            "bias_t_enabled": (0.0, 1.0),
            "rf_notch_enabled": (0.0, 1.0),
            "rf_dab_notch_enabled": (0.0, 1.0),
            "hdr_enabled": (0.0, 1.0),
            "hdr_bw": (0.0, 3.0),
            "lna_state": (0.0, 27.0),
            "if_type": (0.0, 3.0),
        }
        # RSPdx exposes several ADC rates.  The previous implementation only
        # advertised the 2 MS/s default, which made the Sampling combo look
        # broken even though the native API accepts the higher RSPdx modes.
        # Keep this list limited to the documented RSPdx operating points;
        # the API remains the final authority when a mode is opened.
        sample_rates = (2_000_000, 6_000_000, 8_000_000, 10_000_000)
        return DeviceCapabilities(
            device_id,
            ((1_000, 2_000_000_001),),
            sample_rates,
            (200_000, 300_000, 600_000, 1_536_000, 5_000_000, 6_000_000, 7_000_000, 8_000_000),
            antennas,
            gains,
            True,
            (SampleFormat.CS16,),
        )

    def open(self, device_id: str) -> None:
        if device_id != self.DEVICE_ID:
            raise KeyError(device_id)
        self._dll = self._load()
        self._opened = True

    def _load(self) -> ctypes.CDLL:
        bundled_api = Path(sys._MEIPASS) / "sdrplay_api.dll" if hasattr(sys, "_MEIPASS") else None
        api_dll = bundled_api if bundled_api and bundled_api.exists() else Path(r"C:\Program Files\SDRplay\API\x64\sdrplay_api.dll")
        api_dir = api_dll.parent
        if hasattr(os, "add_dll_directory") and api_dir.exists():
            self._dll_directory = os.add_dll_directory(str(api_dir))
        if api_dll.exists():
            # Précharge une seule copie officielle : embarquée dans le portable,
            # installée SDRplay en développement. Cela évite le mélange PothosSDR.
            self._api_dll = ctypes.CDLL(str(api_dll))
        dll = ctypes.CDLL(str(self._dll_path))
        dll.sdb_open.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_int, ctypes.c_int, ctypes.c_int, self.CALLBACK, ctypes.c_void_p]
        dll.sdb_open.restype = ctypes.c_int
        dll.sdb_close.restype = ctypes.c_int
        dll.sdb_read_iq.argtypes = [ctypes.POINTER(ctypes.c_int16), ctypes.c_uint32,
                                    ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint64), ctypes.c_int]
        dll.sdb_read_iq.restype = ctypes.c_int
        dll.sdb_set_frequency.argtypes = [ctypes.c_double]; dll.sdb_set_frequency.restype = ctypes.c_int
        dll.sdb_set_gain.argtypes = [ctypes.c_int, ctypes.c_int]; dll.sdb_set_gain.restype = ctypes.c_int
        dll.sdb_set_bandwidth.argtypes = [ctypes.c_int]; dll.sdb_set_bandwidth.restype = ctypes.c_int
        dll.sdb_set_options.argtypes = [ctypes.c_int] * 8; dll.sdb_set_options.restype = ctypes.c_int
        dll.sdb_last_error.restype = ctypes.c_char_p
        dll.sdb_serial.restype = ctypes.c_char_p
        dll.sdb_api_version.restype = ctypes.c_float
        return dll

    def _check(self, code: int, operation: str) -> None:
        if code != 0:
            raw = self._dll.sdb_last_error() if self._dll else None
            detail = raw.decode("utf-8", errors="replace") if raw else f"code {code}"
            raise RuntimeError(f"{operation}: {detail}")

    def configure(self, request: RadioConfig) -> RadioConfig:
        request.validate()
        if not 20 <= request.gain_reduction_db <= 59:
            raise ValueError("SDRplay gain reduction must be between 20 and 59 dB")
        if not self._opened:
            raise RuntimeError("native SDRplay source is not open")
        if self._active:
            if request.sample_rate_sps != self._config.sample_rate_sps:
                raise ValueError("changing sample rate requires a source restart")
            if request.center_frequency_hz != self._config.center_frequency_hz:
                self._check(self._dll.sdb_set_frequency(float(request.center_frequency_hz)), "set frequency")
            if (request.gain_reduction_db, request.agc_enabled) != (self._config.gain_reduction_db, self._config.agc_enabled):
                self._check(self._dll.sdb_set_gain(request.gain_reduction_db, int(request.agc_enabled)), "set gain")
            if request.bandwidth_hz != self._config.bandwidth_hz:
                self._check(self._dll.sdb_set_bandwidth(int(round(request.bandwidth_hz / 1000))), "set bandwidth")
            if (request.antenna, dict(request.gains)) != (self._config.antenna, dict(self._config.gains)):
                self._set_options(request)
        self._config = request
        return request

    def _set_options(self, config: RadioConfig) -> None:
        antenna = {"A": 0, "B": 1, "C": 2}.get(config.antenna or "A", 0)
        gains = config.gains
        self._check(self._dll.sdb_set_options(
            antenna,
            int(bool(gains.get("bias_t_enabled", 0))),
            int(bool(gains.get("rf_notch_enabled", 0))),
            int(bool(gains.get("rf_dab_notch_enabled", 0))),
            int(bool(gains.get("hdr_enabled", 0))),
            max(0, min(3, int(float(gains.get("hdr_bw", 3))))),
            max(0, min(27, int(float(gains.get("lna_state", 0))))),
            max(0, min(3, int(float(gains.get("if_type", 0))))),
        ), "set RSPdx options")

    def apply_config(self, config: RadioConfig) -> None:
        self.configure(config)

    def start(self, on_block: BlockCallback, on_error: ErrorCallback | None = None) -> None:
        if not self._dll or not self._opened:
            raise RuntimeError("native SDRplay source is not open")
        if self._active:
            raise RuntimeError("source already active")
        self._callback, self._error_callback, self._error = on_block, on_error, None
        code = self._dll.sdb_open(
            float(self._config.sample_rate_sps),
            float(self._config.center_frequency_hz),
            int(round(self._config.bandwidth_hz / 1000)),
            self._config.gain_reduction_db,
            int(self._config.agc_enabled),
            # L'ABI historique attend toujours une instance CFUNCTYPE. Le
            # callback est conservé comme bouchon de compatibilité ; la DLL
            # native ne l'invoque plus et livre les blocs via sdb_read_iq().
            self._native_callback,
            None,
        )
        self._check(code, "SDRplay open")
        self._active = True
        self._reader_stop.clear()
        self._reader_thread = threading.Thread(target=self._read_loop, name="sdrplay-rx", daemon=True)
        self._reader_thread.start()
        if self._config.antenna or self._config.gains:
            self._set_options(self._config)

    def stop(self) -> None:
        # Signale d'abord la sortie afin que le réveil -100 provoqué par
        # sdb_close ne soit pas remonté comme une erreur RX normale.
        self._reader_stop.set()
        if self._dll and self._active:
            self._check(self._dll.sdb_close(), "SDRplay close")
        self._active = False
        thread = self._reader_thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        self._reader_thread = None
        self._callback = None

    def close(self) -> None:
        self.stop()
        self._dll = None
        self._api_dll = None
        self._opened = False

    def _on_iq(self, samples, sample_count: int, first_sample: int, context) -> None:
        try:
            if self._callback and sample_count:
                array = np.ctypeslib.as_array(samples, shape=(sample_count * 2,))
                self._callback(SourceChunk(
                    memoryview(array).cast("B"), int(sample_count), int(first_sample), int(first_sample),
                    TimeDomain.DEVICE_RELATIVE, TimestampOrigin.HARDWARE,
                ))
        except BaseException as exc:
            self._error = exc
            if self._error_callback:
                self._error_callback(exc)

    def _read_loop(self) -> None:
        """Consomme la file native; aucune transition SDRplay->Python ne se
        produit dans le callback du driver, ce qui rend les mises à jour RF
        indépendantes du GIL et du traitement DSP."""
        if not self._dll:
            return
        capacity = 1_048_576
        buffer = np.empty(capacity * 2, dtype=np.int16)
        sample_count = ctypes.c_uint32(0)
        first_sample = ctypes.c_uint64(0)
        pointer = buffer.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
        # La file native SDRplay renvoie généralement des paquets courts
        # (environ 1008 IQ à 2 MS/s). Les propager tels quels ferait plusieurs
        # milliers d'écritures ring/UDP par seconde et surcharge le dispatcher
        # Python. On regroupe donc les retours en blocs de la taille du ring
        # logique, tout en conservant l'index d'échantillon pour détecter un
        # trou matériel.
        aggregate_target = 4096
        pending = bytearray()
        pending_first_sample = 0
        pending_sample_count = 0

        def enqueue_chunk(payload: bytes, first: int, count: int,
                          discontinuity=Discontinuity.NONE,
                          lost_samples: int | None = 0) -> None:
            if self._callback:
                self._callback(SourceChunk(
                    payload=memoryview(payload),
                    sample_count=count,
                    first_sample_index=first,
                    timestamp_ns=0,
                    time_domain=TimeDomain.DEVICE_RELATIVE,
                    timestamp_origin=TimestampOrigin.HARDWARE,
                    discontinuity=discontinuity,
                    lost_samples=lost_samples,
                ))

        def emit_pending(discontinuity=Discontinuity.NONE, lost_samples=0) -> None:
            nonlocal pending, pending_first_sample, pending_sample_count
            if pending_sample_count <= 0:
                return
            enqueue_chunk(bytes(pending), pending_first_sample, pending_sample_count,
                          discontinuity, lost_samples)
            pending.clear()
            pending_sample_count = 0

        while not self._reader_stop.is_set():
            try:
                result = self._dll.sdb_read_iq(pointer, capacity,
                                               ctypes.byref(sample_count),
                                               ctypes.byref(first_sample), 100)
                if result == 0:
                    continue
                if result < 0:
                    if not self._reader_stop.is_set() and self._error_callback:
                        self._error_callback(RuntimeError(f"SDRplay read queue: code {result}"))
                    return
                count = int(sample_count.value)
                if count <= 0 or not self._callback:
                    continue
                first = int(first_sample.value)
                if pending_sample_count:
                    expected = pending_first_sample + pending_sample_count
                    if first != expected:
                        lost = first - expected
                        emit_pending(
                            Discontinuity.SOURCE_LOSS,
                            lost if lost > 0 else None,
                        )
                if not pending_sample_count:
                    pending_first_sample = first
                # Le buffer C est réutilisé au prochain appel : copier ici est
                # nécessaire, mais une seule copie par paquet natif au lieu
                # d'une copie/écriture ring par paquet.
                pending.extend(memoryview(buffer[:count * 2]).cast("B"))
                pending_sample_count += count
                while pending_sample_count >= aggregate_target:
                    chunk_bytes = aggregate_target * SampleFormat.CS16.bytes_per_iq
                    enqueue_chunk(bytes(pending[:chunk_bytes]), pending_first_sample,
                                  aggregate_target)
                    del pending[:chunk_bytes]
                    pending_first_sample += aggregate_target
                    pending_sample_count -= aggregate_target
            except BaseException as exc:
                self._error = exc
                if self._error_callback:
                    self._error_callback(exc)
                return
