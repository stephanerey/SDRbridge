"""Sous-ensemble SoapySDR en lecture seule pour ANTRACK.

Le shim consomme un profil DSP partagé SDRbridge. Il n'ouvre aucun SDR et
n'implémente aucune mutation RF cliente.
"""
from __future__ import annotations

import ctypes
import json
from multiprocessing import shared_memory
from pathlib import Path
import socket
import struct
import time

import numpy as np

SOAPY_SDR_TX = 0
SOAPY_SDR_RX = 1
SOAPY_SDR_CF32 = "CF32"
SOAPY_SDR_TIMEOUT = -1
SOAPY_SDR_STREAM_ERROR = -2
SOAPY_SDR_OVERFLOW = -4
EMPTY = (1 << 64) - 1
GLOBAL = struct.Struct("<4sIIIIIIIQQ")
SLOT = struct.Struct("<IIQQQQIIQII")
HEADER_BYTES = 128
SLOT_HEADER_BYTES = 64


class StreamResult:
    def __init__(self, ret: int, flags: int = 0, timeNs: int = 0):
        self.ret, self.flags, self.timeNs = ret, flags, timeNs


def _atomic_library():
    candidates = (
        Path(__file__).with_name("sdr_ring_atomic.dll"),
        Path(__file__).resolve().parents[2] / "native" / "build" / "ring_atomic-x64" / "Release" / "sdr_ring_atomic.dll",
    )
    path = next((item for item in candidates if item.exists()), None)
    if path is None:
        raise RuntimeError("sdr_ring_atomic.dll is required by the SDBR v2 reader")
    dll = ctypes.CDLL(str(path))
    dll.sdb_guard_load.argtypes = [ctypes.c_void_p]; dll.sdb_guard_load.restype = ctypes.c_uint32
    return dll


_ATOMIC = None


def _guard_load(buffer, offset):
    global _ATOMIC
    if _ATOMIC is None:
        _ATOMIC = _atomic_library()
    address = ctypes.addressof(ctypes.c_ubyte.from_buffer(buffer, offset))
    return int(_ATOMIC.sdb_guard_load(address))


def listModules():
    return ["sdr_bridge"]


def Device_enumerate(args=None):
    try:
        sock = socket.create_connection(("127.0.0.1", 47631), timeout=0.5)
        stream = sock.makefile("rwb")
        stream.write(b'{"action":"status"}\n'); stream.flush()
        response = json.loads(stream.readline())
        stream.close(); sock.close()
        if response.get("ok"):
            return [{"driver": "sdr_bridge", "label": "SDRbridge Local IQ (lecture seule)", "serial": "SDRBRIDGE"}]
    except OSError:
        pass
    return []


class Device:
    def __init__(self, args=None):
        self._sock = None; self._file = None; self._shm = None
        self._client_id = None; self._descriptor = None
        self._slots = self._slot_stride = self._max_samples = 0
        self._next = 0; self._drops = 0; self._samples = 0; self._last_heartbeat = 0.0
        self._requested_rate = 192_000
        self._fifo = np.empty(0, dtype=np.complex64)
        self._active = False
        self._connect_profile()

    def _request(self, payload):
        self._file.write(json.dumps(payload, separators=(",", ":")).encode() + b"\n"); self._file.flush()
        response = json.loads(self._file.readline())
        if not response.get("ok"):
            raise RuntimeError(response.get("error", "SDRbridge request failed"))
        return response

    def _disconnect(self):
        if self._shm is not None:
            self._shm.close(); self._shm = None
        if self._file is not None:
            self._file.close(); self._file = None
        if self._sock is not None:
            self._sock.close(); self._sock = None

    def _connect_profile(self):
        self._disconnect()
        rate = int(round(self._requested_rate))
        if rate not in {96_000, 192_000}:
            raise RuntimeError("SDRbridge ANTRACK profile supports 96 or 192 kS/s")
        profile = "antrack-96k" if rate == 96_000 else "antrack-192k"
        self._sock = socket.create_connection(("127.0.0.1", 47631), timeout=3)
        self._file = self._sock.makefile("rwb")
        response = self._request({"action": "register", "name": "ANTRACK", "profile_id": profile, "profile_revision": 1})
        descriptor = response["ring"]
        if int(descriptor.get("version", 0)) != 2 or descriptor.get("sample_format") != "ci16_le":
            raise RuntimeError("ANTRACK requires SDBR v2 CS16")
        self._client_id = response["client_id"]
        self._descriptor = descriptor
        self._slots = int(descriptor["slot_count"]); self._slot_stride = int(descriptor["slot_stride"])
        self._max_samples = int(descriptor["max_samples"])
        self._shm = shared_memory.SharedMemory(name=descriptor["name"], create=False)
        fields = GLOBAL.unpack_from(self._shm.buf, 0)
        if fields[0] != b"SDBR" or fields[1] != 2 or fields[2] != HEADER_BYTES or fields[3] != self._slots or fields[4] != self._slot_stride:
            raise RuntimeError("invalid SDBR v2 descriptor")
        latest = self._read_latest()
        self._next = 0 if latest == EMPTY else latest + 1
        self._fifo = np.empty(0, dtype=np.complex64)

    def _read_latest(self):
        for _ in range(3):
            before = _guard_load(self._shm.buf, 28)
            if before & 1:
                continue
            latest = struct.unpack_from("<Q", self._shm.buf, 32)[0]
            after = _guard_load(self._shm.buf, 28)
            if before == after and not after & 1:
                return latest
        return EMPTY

    def listAntennas(self, direction, channel): return ["SDRbridge"]
    def listGains(self, direction, channel): return ["SERVER_READ_ONLY"]
    def listSampleRates(self, direction, channel): return [192000.0, 96000.0]
    def getSettingInfo(self): return []
    def writeSetting(self, key, value): return 0
    def setGain(self, direction, channel, *args): return 0
    def setGainMode(self, direction, channel, automatic): return 0
    def setFrequencyCorrection(self, direction, channel, value): return 0
    def setFrequency(self, direction, channel, value): return 0
    def setAntenna(self, direction, channel, name): return 0

    def setSampleRate(self, direction, channel, rate):
        rate = int(round(rate))
        if rate not in {96_000, 192_000}:
            raise RuntimeError("unsupported read-only SDRbridge profile rate")
        if rate != int(self._requested_rate):
            if self._active:
                raise RuntimeError("deactivate stream before changing SDRbridge profile")
            self._requested_rate = rate
            self._connect_profile()
        return 0

    def setupStream(self, direction, fmt, channels=None, args=None):
        if direction != SOAPY_SDR_RX or fmt != SOAPY_SDR_CF32:
            raise RuntimeError("SDRbridge ANTRACK shim supports RX CF32 only")
        return self

    def activateStream(self, stream, flags=0, timeNs=0, numElems=0): self._active = True; return 0
    def deactivateStream(self, stream, flags=0, timeNs=0): self._active = False; return 0
    def closeStream(self, stream): return 0

    def _read_block(self, timeout_s):
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            latest = self._read_latest()
            if latest != EMPTY and latest >= self._next:
                oldest = max(0, latest - self._slots + 1)
                if self._next < oldest:
                    self._drops += oldest - self._next; self._next = oldest
                offset = HEADER_BYTES + (self._next % self._slots) * self._slot_stride
                coherent = None
                for _ in range(3):
                    before = _guard_load(self._shm.buf, offset)
                    if before & 1:
                        continue
                    fields = SLOT.unpack_from(self._shm.buf, offset)
                    count, sequence = fields[1], fields[2]
                    if sequence != self._next or not 1 <= count <= self._max_samples:
                        break
                    raw = bytes(self._shm.buf[offset + SLOT_HEADER_BYTES:offset + SLOT_HEADER_BYTES + count * 4])
                    after = _guard_load(self._shm.buf, offset)
                    if before == after and not after & 1:
                        coherent = (raw, count); break
                self._next += 1
                if coherent:
                    raw, count = coherent; self._samples += count
                    pairs = np.frombuffer(raw, dtype="<i2").reshape(-1, 2).astype(np.float32)
                    return ((pairs[:, 0] + 1j * pairs[:, 1]) / 32768.0).astype(np.complex64)
                self._drops += 1
            time.sleep(0.001)
        return None

    def readStream(self, stream, buffs, numElems, timeoutUs=100000):
        if not self._active:
            return StreamResult(SOAPY_SDR_STREAM_ERROR)
        deadline = time.monotonic() + timeoutUs / 1_000_000
        while len(self._fifo) < numElems:
            block = self._read_block(max(0.001, deadline - time.monotonic()))
            if block is None:
                return StreamResult(SOAPY_SDR_TIMEOUT)
            self._fifo = np.concatenate((self._fifo, block))
            if len(self._fifo) > 65_536:
                self._fifo = self._fifo[-65_536:]; self._drops += 1
        buffs[0][:numElems] = self._fifo[:numElems]
        self._fifo = self._fifo[numElems:]
        now = time.monotonic()
        if now - self._last_heartbeat >= 1:
            self._request({"action": "heartbeat", "client_id": self._client_id, "sequence": self._next - 1, "samples": self._samples, "dropped": self._drops})
            self._last_heartbeat = now
        return StreamResult(numElems)

    def __del__(self):
        try: self._disconnect()
        except Exception: pass


Device.enumerate = staticmethod(Device_enumerate)
