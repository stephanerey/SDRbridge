"""Small ctypes-backed subset of the SoapySDR Python API.

This module is intentionally narrow: it covers the API surface used by Antrack's
SDR client and loads the SoapySDR DLLs from a local PothosSDR installation.
"""

from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SOAPY_SDR_TX = 0
SOAPY_SDR_RX = 1
SOAPY_SDR_CF32 = "CF32"
SOAPY_SDR_TIMEOUT = -1
SOAPY_SDR_STREAM_ERROR = -2
SOAPY_SDR_CORRUPTION = -3
SOAPY_SDR_OVERFLOW = -4
SOAPY_SDR_NOT_SUPPORTED = -5
SOAPY_SDR_TIME_ERROR = -6
SOAPY_SDR_UNDERFLOW = -7


class _Range(ctypes.Structure):
    _fields_ = [
        ("minimum", ctypes.c_double),
        ("maximum", ctypes.c_double),
        ("step", ctypes.c_double),
    ]


class _Kwargs(ctypes.Structure):
    _fields_ = [
        ("size", ctypes.c_size_t),
        ("keys", ctypes.POINTER(ctypes.c_char_p)),
        ("vals", ctypes.POINTER(ctypes.c_char_p)),
    ]


class _ArgInfo(ctypes.Structure):
    _fields_ = [
        ("key", ctypes.c_char_p),
        ("value", ctypes.c_char_p),
        ("name", ctypes.c_char_p),
        ("description", ctypes.c_char_p),
        ("units", ctypes.c_char_p),
        ("type", ctypes.c_int),
        ("range", _Range),
        ("numOptions", ctypes.c_size_t),
        ("options", ctypes.POINTER(ctypes.c_char_p)),
        ("optionNames", ctypes.POINTER(ctypes.c_char_p)),
    ]


@dataclass
class ArgInfo:
    key: str
    value: str = ""
    name: str = ""
    description: str = ""
    units: str = ""
    type: int = 0
    range: tuple[float, float, float] = (0.0, 0.0, 0.0)
    options: list[str] | None = None
    optionNames: list[str] | None = None


class StreamResult:
    def __init__(self, ret: int, flags: int = 0, timeNs: int = 0) -> None:
        self.ret = ret
        self.flags = flags
        self.timeNs = timeNs


def _decode(value: bytes | None) -> str:
    return value.decode("utf-8", errors="replace") if value else ""


def _markup(args: dict[str, Any] | None) -> bytes:
    if not args:
        return b""
    return ",".join(f"{key}={value}" for key, value in args.items()).encode("utf-8")


def _pothos_root() -> Path:
    env_root = os.environ.get("POTHOSSDR_ROOT")
    candidates = [
        Path(env_root) if env_root else None,
        Path(r"C:\Program Files\PothosSDR"),
        Path(r"C:\PothosSDR"),
    ]
    for candidate in candidates:
        if candidate and (candidate / "bin" / "SoapySDR.dll").exists():
            return candidate
    raise ImportError("SoapySDR.dll not found. Install PothosSDR first.")


_ROOT = _pothos_root()
_BIN = _ROOT / "bin"
_MODULES = _ROOT / "lib" / "SoapySDR" / "modules0.8"
_SDRPLAY_API = Path(r"C:\Program Files\SDRplay\API\x64")
path_parts = [str(_BIN)]
if (_SDRPLAY_API / "sdrplay_api.dll").exists():
    path_parts.insert(0, str(_SDRPLAY_API))
os.environ["PATH"] = ";".join(path_parts + [os.environ.get("PATH", "")])
if hasattr(os, "add_dll_directory"):
    if (_SDRPLAY_API / "sdrplay_api.dll").exists():
        os.add_dll_directory(str(_SDRPLAY_API))
    os.add_dll_directory(str(_BIN))

if (_SDRPLAY_API / "sdrplay_api.dll").exists():
    # PothosSDR ships an older SDRplay API DLL. Loading the installed SDRplay
    # API first keeps the SoapySDRPlay module aligned with the running service.
    ctypes.CDLL(str(_SDRPLAY_API / "sdrplay_api.dll"))

_lib = ctypes.CDLL(str(_BIN / "SoapySDR.dll"))


_lib.SoapySDRDevice_lastError.restype = ctypes.c_char_p
_lib.SoapySDRDevice_enumerateStrArgs.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_size_t)]
_lib.SoapySDRDevice_enumerateStrArgs.restype = ctypes.POINTER(_Kwargs)
_lib.SoapySDRKwargsList_clear.argtypes = [ctypes.POINTER(_Kwargs), ctypes.c_size_t]
_lib.SoapySDRDevice_makeStrArgs.argtypes = [ctypes.c_char_p]
_lib.SoapySDRDevice_makeStrArgs.restype = ctypes.c_void_p
_lib.SoapySDRDevice_unmake.argtypes = [ctypes.c_void_p]
_lib.SoapySDRDevice_unmake.restype = ctypes.c_int
_lib.SoapySDRStrings_clear.argtypes = [ctypes.POINTER(ctypes.POINTER(ctypes.c_char_p)), ctypes.c_size_t]
_lib.SoapySDR_free.argtypes = [ctypes.c_void_p]
_lib.SoapySDR_listModules.argtypes = [ctypes.POINTER(ctypes.c_size_t)]
_lib.SoapySDR_listModules.restype = ctypes.POINTER(ctypes.c_char_p)
_lib.SoapySDR_loadModules.argtypes = []

_lib.SoapySDRDevice_listAntennas.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
_lib.SoapySDRDevice_listAntennas.restype = ctypes.POINTER(ctypes.c_char_p)
_lib.SoapySDRDevice_listGains.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
_lib.SoapySDRDevice_listGains.restype = ctypes.POINTER(ctypes.c_char_p)
_lib.SoapySDRDevice_listSampleRates.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
_lib.SoapySDRDevice_listSampleRates.restype = ctypes.POINTER(ctypes.c_double)
_lib.SoapySDRDevice_getSettingInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)]
_lib.SoapySDRDevice_getSettingInfo.restype = ctypes.POINTER(_ArgInfo)
_lib.SoapySDRArgInfoList_clear.argtypes = [ctypes.POINTER(_ArgInfo), ctypes.c_size_t]

_lib.SoapySDRDevice_setAntenna.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.c_char_p]
_lib.SoapySDRDevice_setGainMode.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.c_bool]
_lib.SoapySDRDevice_setGain.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.c_double]
_lib.SoapySDRDevice_setGainElement.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_double]
_lib.SoapySDRDevice_setFrequencyCorrection.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.c_double]
_lib.SoapySDRDevice_setSampleRate.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.c_double]
_lib.SoapySDRDevice_setBandwidth.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.c_double]
_lib.SoapySDRDevice_setFrequency.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.c_double, ctypes.c_void_p]
_lib.SoapySDRDevice_writeSetting.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
_lib.SoapySDRDevice_getFrequency.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t]
_lib.SoapySDRDevice_getFrequency.restype = ctypes.c_double
_lib.SoapySDRDevice_getSampleRate.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t]
_lib.SoapySDRDevice_getSampleRate.restype = ctypes.c_double
_lib.SoapySDRDevice_getBandwidth.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t]
_lib.SoapySDRDevice_getBandwidth.restype = ctypes.c_double
_lib.SoapySDRDevice_getGainElementRange.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.c_char_p]
_lib.SoapySDRDevice_getGainElementRange.restype = _Range
_lib.SoapySDRDevice_getFrequencyRange.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
_lib.SoapySDRDevice_getFrequencyRange.restype = ctypes.POINTER(_Range)
_lib.SoapySDRDevice_listBandwidths.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
_lib.SoapySDRDevice_listBandwidths.restype = ctypes.POINTER(ctypes.c_double)

_lib.SoapySDRDevice_setupStream.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p]
_lib.SoapySDRDevice_setupStream.restype = ctypes.c_void_p
_lib.SoapySDRDevice_activateStream.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_longlong, ctypes.c_size_t]
_lib.SoapySDRDevice_deactivateStream.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_longlong]
_lib.SoapySDRDevice_closeStream.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_lib.SoapySDRDevice_readStream.argtypes = [
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_void_p),
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_int),
    ctypes.POINTER(ctypes.c_longlong),
    ctypes.c_long,
]


def _last_error() -> str:
    return _decode(_lib.SoapySDRDevice_lastError()) or "SoapySDR call failed"


def _check(code: int) -> int:
    if int(code) < 0:
        raise RuntimeError(f"{_last_error()} ({code})")
    return int(code)


def _string_list(func: Any, *args: Any) -> list[str]:
    length = ctypes.c_size_t()
    result = func(*args, ctypes.byref(length))
    values = [_decode(result[index]) for index in range(length.value)] if result else []
    if result:
        holder = ctypes.pointer(result)
        _lib.SoapySDRStrings_clear(holder, length.value)
    return values


def listModules() -> list[str]:
    length = ctypes.c_size_t()
    result = _lib.SoapySDR_listModules(ctypes.byref(length))
    values = [_decode(result[index]) for index in range(length.value)] if result else []
    if result:
        holder = ctypes.pointer(result)
        _lib.SoapySDRStrings_clear(holder, length.value)
    return values


def Device_enumerate(args: dict[str, Any] | None = None) -> list[dict[str, str]]:
    _lib.SoapySDR_loadModules()
    length = ctypes.c_size_t()
    result = _lib.SoapySDRDevice_enumerateStrArgs(_markup(args), ctypes.byref(length))
    devices: list[dict[str, str]] = []
    if result:
        for index in range(length.value):
            entry = result[index]
            devices.append(
                {
                    _decode(entry.keys[item]): _decode(entry.vals[item])
                    for item in range(entry.size)
                }
            )
        _lib.SoapySDRKwargsList_clear(result, length.value)
    return devices


class Device:
    def __init__(self, args: dict[str, Any] | None = None) -> None:
        _lib.SoapySDR_loadModules()
        self._device = _lib.SoapySDRDevice_makeStrArgs(_markup(args))
        if not self._device:
            raise RuntimeError(_last_error())

    def __del__(self) -> None:
        device = getattr(self, "_device", None)
        if device:
            try:
                _lib.SoapySDRDevice_unmake(device)
            except Exception:
                pass
            self._device = None

    def listAntennas(self, direction: int, channel: int) -> list[str]:
        return _string_list(_lib.SoapySDRDevice_listAntennas, self._device, direction, channel)

    def listGains(self, direction: int, channel: int) -> list[str]:
        return _string_list(_lib.SoapySDRDevice_listGains, self._device, direction, channel)

    def listSampleRates(self, direction: int, channel: int) -> list[float]:
        length = ctypes.c_size_t()
        result = _lib.SoapySDRDevice_listSampleRates(self._device, direction, channel, ctypes.byref(length))
        values = [float(result[index]) for index in range(length.value)] if result else []
        if result:
            _lib.SoapySDR_free(result)
        return values

    def getSettingInfo(self) -> list[ArgInfo]:
        length = ctypes.c_size_t()
        result = _lib.SoapySDRDevice_getSettingInfo(self._device, ctypes.byref(length))
        values: list[ArgInfo] = []
        if result:
            for index in range(length.value):
                entry = result[index]
                values.append(
                    ArgInfo(
                        key=_decode(entry.key),
                        value=_decode(entry.value),
                        name=_decode(entry.name),
                        description=_decode(entry.description),
                        units=_decode(entry.units),
                        type=int(entry.type),
                        range=(entry.range.minimum, entry.range.maximum, entry.range.step),
                        options=[_decode(entry.options[i]) for i in range(entry.numOptions)] if entry.options else [],
                        optionNames=[_decode(entry.optionNames[i]) for i in range(entry.numOptions)] if entry.optionNames else [],
                    )
                )
            _lib.SoapySDRArgInfoList_clear(result, length.value)
        return values

    def writeSetting(self, key: str, value: str) -> int:
        return _check(_lib.SoapySDRDevice_writeSetting(self._device, key.encode(), str(value).encode()))

    def setGain(self, direction: int, channel: int, *args: Any) -> int:
        if len(args) == 1:
            return _check(_lib.SoapySDRDevice_setGain(self._device, direction, channel, float(args[0])))
        if len(args) == 2:
            return _check(_lib.SoapySDRDevice_setGainElement(self._device, direction, channel, str(args[0]).encode(), float(args[1])))
        raise TypeError("setGain expects value or name, value")

    def setGainMode(self, direction: int, channel: int, automatic: bool) -> int:
        return _check(_lib.SoapySDRDevice_setGainMode(self._device, direction, channel, bool(automatic)))

    def setFrequencyCorrection(self, direction: int, channel: int, value: float) -> int:
        return _check(_lib.SoapySDRDevice_setFrequencyCorrection(self._device, direction, channel, float(value)))

    def setSampleRate(self, direction: int, channel: int, rate: float) -> int:
        return _check(_lib.SoapySDRDevice_setSampleRate(self._device, direction, channel, float(rate)))

    def setBandwidth(self, direction: int, channel: int, bandwidth: float) -> int:
        return _check(_lib.SoapySDRDevice_setBandwidth(self._device, direction, channel, float(bandwidth)))

    def setFrequency(self, direction: int, channel: int, frequency: float) -> int:
        return _check(_lib.SoapySDRDevice_setFrequency(self._device, direction, channel, float(frequency), None))

    def setAntenna(self, direction: int, channel: int, name: str) -> int:
        return _check(_lib.SoapySDRDevice_setAntenna(self._device, direction, channel, str(name).encode()))

    def getFrequency(self, direction: int, channel: int) -> float:
        return float(_lib.SoapySDRDevice_getFrequency(self._device, direction, channel))

    def getSampleRate(self, direction: int, channel: int) -> float:
        return float(_lib.SoapySDRDevice_getSampleRate(self._device, direction, channel))

    def getBandwidth(self, direction: int, channel: int) -> float:
        return float(_lib.SoapySDRDevice_getBandwidth(self._device, direction, channel))

    def getGainRange(self, direction: int, channel: int, name: str) -> tuple[float, float, float]:
        value = _lib.SoapySDRDevice_getGainElementRange(self._device, direction, channel, str(name).encode())
        return float(value.minimum), float(value.maximum), float(value.step)

    def getFrequencyRanges(self, direction: int, channel: int) -> list[tuple[float, float, float]]:
        length = ctypes.c_size_t()
        result = _lib.SoapySDRDevice_getFrequencyRange(self._device, direction, channel, ctypes.byref(length))
        values = [(float(result[i].minimum), float(result[i].maximum), float(result[i].step)) for i in range(length.value)] if result else []
        if result:
            _lib.SoapySDR_free(result)
        return values

    def listBandwidths(self, direction: int, channel: int) -> list[float]:
        length = ctypes.c_size_t()
        result = _lib.SoapySDRDevice_listBandwidths(self._device, direction, channel, ctypes.byref(length))
        values = [float(result[i]) for i in range(length.value)] if result else []
        if result:
            _lib.SoapySDR_free(result)
        return values

    def setupStream(self, direction: int, fmt: str, channels: Any = None, args: Any = None) -> ctypes.c_void_p:
        stream = _lib.SoapySDRDevice_setupStream(self._device, direction, str(fmt).encode(), None, 0, None)
        if not stream:
            raise RuntimeError(_last_error())
        return stream

    def activateStream(self, stream: ctypes.c_void_p, flags: int = 0, timeNs: int = 0, numElems: int = 0) -> int:
        return _check(_lib.SoapySDRDevice_activateStream(self._device, stream, flags, timeNs, numElems))

    def deactivateStream(self, stream: ctypes.c_void_p, flags: int = 0, timeNs: int = 0) -> int:
        return _check(_lib.SoapySDRDevice_deactivateStream(self._device, stream, flags, timeNs))

    def closeStream(self, stream: ctypes.c_void_p) -> int:
        return _check(_lib.SoapySDRDevice_closeStream(self._device, stream))

    def readStream(self, stream: ctypes.c_void_p, buffs: list[Any], numElems: int, timeoutUs: int = 100000) -> StreamResult:
        ptrs = (ctypes.c_void_p * len(buffs))()
        for index, buffer in enumerate(buffs):
            ptrs[index] = ctypes.c_void_p(buffer.ctypes.data)
        flags = ctypes.c_int(0)
        time_ns = ctypes.c_longlong(0)
        ret = _lib.SoapySDRDevice_readStream(
            self._device,
            stream,
            ptrs,
            numElems,
            ctypes.byref(flags),
            ctypes.byref(time_ns),
            int(timeoutUs),
        )
        return StreamResult(int(ret), int(flags.value), int(time_ns.value))
