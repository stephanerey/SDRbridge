from __future__ import annotations

from dataclasses import dataclass
import math
import queue
import socket
import struct
import threading
import time

import numpy as np

from .model import Discontinuity, IQBlock, SampleFormat, StreamProfile, TimeDomain, TimestampOrigin

HEADER = struct.Struct(">4sBBHHBBIQQQQIIQII")
MAGIC = b"SDBU"
VERSION = 2
HEADER_BYTES = 72
DEFAULT_DATAGRAM_BYTES = 1200
LOOPBACK_RAW_DATAGRAM_BYTES = 8192
MAX_UDP_DATAGRAM_BYTES = 65_507
# Keep the prefill below the 64-slot ring capacity even when a native driver
# returns short blocks (the ring would otherwise overrun before the first
# packet is released).
LOOPBACK_RAW_BUFFER_BLOCKS = 8

# QMAP 0.6 consumes the historic Linrad UDP structure directly.  The C/C++
# layout is fixed at 24 header bytes followed by 348 interleaved int16 I/Q
# samples (1392 bytes), for a total of 1416 bytes per datagram.
QMAP_SAMPLE_RATE_SPS = 96_000
QMAP_PACKET_SAMPLES = 348
QMAP_HEADER = struct.Struct("<difiHbc")
QMAP_PACKET_BYTES = QMAP_HEADER.size + QMAP_PACKET_SAMPLES * SampleFormat.CS16.bytes_per_iq

FLAG_TIME_VALID = 1 << 0
FLAG_HARDWARE_ORIGIN = 1 << 1
FLAG_DISCONTINUITY = 1 << 2
FLAG_REPLAY = 1 << 3
KNOWN_FLAGS = FLAG_TIME_VALID | FLAG_HARDWARE_ORIGIN | FLAG_DISCONTINUITY | FLAG_REPLAY


@dataclass(frozen=True, slots=True)
class NativeDatagram:
    sample_format: SampleFormat
    flags: int
    time_domain: TimeDomain
    wire_stream_id: int
    epoch: int
    packet_sequence: int
    first_sample_index: int
    timestamp_ns: int
    config_revision: int
    sample_rate_sps: int
    center_frequency_hz: int
    sample_count: int
    payload: bytes


@dataclass(frozen=True, slots=True)
class QMAPDatagram:
    center_frequency_mhz: float
    milliseconds: int
    user_frequency: float
    sample_pointer: int
    block_sequence: int
    receiver_count: int
    sideband: bytes
    payload: bytes


class QMAPEncoder:
    """Encode 96 kS/s CS16 into the fixed Linrad datagrams used by QMAP."""

    def __init__(self, *, clock_ms=None):
        self._clock_ms = clock_ms or (lambda: int(time.time() * 1000))
        self._pending = bytearray()
        self._stream_key: tuple[int, int, int] | None = None
        self._block_sequence = 0
        self._sample_pointer = 0
        self._phase = 0
        self.discarded_samples = 0

    @property
    def pending_samples(self) -> int:
        return len(self._pending) // SampleFormat.CS16.bytes_per_iq

    def _reset(self, stream_key: tuple[int, int, int]) -> None:
        self.discarded_samples += self.pending_samples
        self._pending.clear()
        self._stream_key = stream_key
        self._block_sequence = 0
        self._sample_pointer = 0
        self._phase = 0

    def encode(self, block: IQBlock) -> list[bytes]:
        if block.sample_format is not SampleFormat.CS16:
            raise ValueError("QMAP/Linrad profile requires CS16")
        if block.sample_rate_sps != QMAP_SAMPLE_RATE_SPS:
            raise ValueError("QMAP/Linrad profile requires exactly 96000 S/s")
        stream_key = (block.epoch, block.center_frequency_hz, block.sample_rate_sps)
        if (self._stream_key != stream_key
                or block.discontinuity is not Discontinuity.NONE):
            self._reset(stream_key)

        pairs = np.frombuffer(block.payload, dtype="<i2").reshape(-1, 2).astype(np.int32)
        # QMAP's FFT convention is the inverse of the source stream.  The
        # Linrad-compatible mapping is (-1)^n * conj(I+jQ).
        sign = 1 - 2 * ((np.arange(block.sample_count, dtype=np.int32) + self._phase) & 1)
        pairs[:, 0] *= sign
        pairs[:, 1] *= -sign
        self._phase = (self._phase + block.sample_count) & 1
        transformed = np.clip(pairs, -32768, 32767).astype("<i2", copy=False)
        self._pending.extend(transformed.tobytes())

        packets: list[bytes] = []
        payload_bytes = QMAP_PACKET_SAMPLES * SampleFormat.CS16.bytes_per_iq
        while len(self._pending) >= payload_bytes:
            payload = bytes(self._pending[:payload_bytes])
            del self._pending[:payload_bytes]
            header = QMAP_HEADER.pack(
                block.center_frequency_hz / 1_000_000.0,
                int(self._clock_ms()) % 86_400_000,
                0.0,
                self._sample_pointer,
                self._block_sequence,
                1,
                b"\x00",
            )
            packets.append(header + payload)
            self._sample_pointer = (self._sample_pointer + QMAP_PACKET_SAMPLES) & 0x7FFFFFFF
            self._block_sequence = (self._block_sequence + 1) & 0xFFFF
        return packets


def parse_qmap_datagram(data: bytes) -> QMAPDatagram:
    if len(data) != QMAP_PACKET_BYTES:
        raise ValueError("QMAP/Linrad datagram must contain exactly 1416 bytes")
    frequency, milliseconds, user_frequency, pointer, sequence, receiver_count, sideband = QMAP_HEADER.unpack_from(data)
    if receiver_count != 1:
        raise ValueError("only the single-receiver QMAP/Linrad layout is supported")
    if not 0 <= milliseconds < 86_400_000:
        raise ValueError("invalid QMAP/Linrad millisecond field")
    return QMAPDatagram(
        frequency, milliseconds, user_frequency, pointer, sequence,
        receiver_count, sideband, data[QMAP_HEADER.size:],
    )


class SDBUEncoder:
    def __init__(self, wire_stream_id: int, max_datagram_bytes: int = DEFAULT_DATAGRAM_BYTES):
        if not 1 <= wire_stream_id <= 0xFFFFFFFF:
            raise ValueError("wire_stream_id must be non-zero uint32")
        if max_datagram_bytes <= HEADER_BYTES:
            raise ValueError("datagram budget is too small")
        self.wire_stream_id = int(wire_stream_id)
        self.max_datagram_bytes = int(max_datagram_bytes)
        self._epoch: int | None = None
        self._packet_sequence = 0

    def encode(self, block: IQBlock) -> list[bytes]:
        bytes_per_iq = block.sample_format.bytes_per_iq
        max_samples = (self.max_datagram_bytes - HEADER_BYTES) // bytes_per_iq
        if max_samples < 1:
            raise ValueError("datagram budget cannot hold one IQ sample")
        if self._epoch != block.epoch:
            self._epoch = block.epoch
            self._packet_sequence = 0
            first_epoch_packet = True
        else:
            first_epoch_packet = False
        packets: list[bytes] = []
        raw = bytes(block.payload)
        for offset in range(0, block.sample_count, max_samples):
            count = min(max_samples, block.sample_count - offset)
            flags = 0
            if block.time_domain is not TimeDomain.UNKNOWN:
                flags |= FLAG_TIME_VALID
            if block.timestamp_origin is TimestampOrigin.HARDWARE:
                flags |= FLAG_HARDWARE_ORIGIN
            if (first_epoch_packet and offset == 0) or block.discontinuity is not Discontinuity.NONE:
                flags |= FLAG_DISCONTINUITY
            if block.time_domain is TimeDomain.REPLAY_RELATIVE:
                flags |= FLAG_REPLAY
            timestamp = 0
            if flags & FLAG_TIME_VALID:
                timestamp = block.timestamp_ns + round(offset * 1_000_000_000 / block.sample_rate_sps)
            header = HEADER.pack(
                MAGIC,
                VERSION,
                block.sample_format.wire_code,
                flags,
                HEADER_BYTES,
                int(block.time_domain),
                0,
                self.wire_stream_id,
                block.epoch,
                self._packet_sequence,
                block.first_sample_index + offset,
                timestamp,
                block.config_revision,
                block.sample_rate_sps,
                block.center_frequency_hz,
                count,
                0,
            )
            start = offset * bytes_per_iq
            packets.append(header + raw[start:start + count * bytes_per_iq])
            self._packet_sequence += 1
        return packets


def parse_datagram(data: bytes) -> NativeDatagram:
    if len(data) < HEADER_BYTES:
        raise ValueError("truncated SDBU datagram")
    fields = HEADER.unpack_from(data)
    (magic, version, format_code, flags, header_bytes, time_domain, reserved8, stream_id,
     epoch, packet_sequence, first_index, timestamp, revision, rate, frequency, count, reserved32) = fields
    if magic != MAGIC or version != VERSION or header_bytes != HEADER_BYTES:
        raise ValueError("unsupported SDBU header")
    if reserved8 or reserved32 or flags & ~KNOWN_FLAGS:
        raise ValueError("reserved SDBU field is non-zero")
    sample_format = SampleFormat.from_wire_code(format_code)
    try:
        domain = TimeDomain(time_domain)
    except ValueError as exc:
        raise ValueError("unknown time domain") from exc
    if stream_id == 0 or revision == 0 or rate == 0 or count == 0:
        raise ValueError("invalid zero-valued SDBU field")
    if bool(flags & FLAG_TIME_VALID) == (domain is TimeDomain.UNKNOWN):
        raise ValueError("incoherent time flags")
    if flags & FLAG_HARDWARE_ORIGIN and not flags & FLAG_TIME_VALID:
        raise ValueError("hardware origin requires valid time")
    expected = HEADER_BYTES + count * sample_format.bytes_per_iq
    if len(data) != expected:
        raise ValueError("SDBU datagram length mismatch")
    return NativeDatagram(
        sample_format, flags, domain, stream_id, epoch, packet_sequence, first_index,
        timestamp, revision, rate, frequency, count, data[HEADER_BYTES:],
    )


class UDPDestination:
    """Destination isolée avec file bornée ; une panne n'affecte pas les autres."""

    def __init__(
        self,
        destination: tuple[str, int],
        *,
        wire_stream_id: int,
        transport: str = "sdbu_v2",
        max_datagram_bytes: int = DEFAULT_DATAGRAM_BYTES,
        queue_blocks: int = 32,
        raw_buffer_blocks: int = 0,
        multicast_interface: str | None = None,
        multicast_loopback: bool = False,
    ):
        if transport not in {"sdbu_v2", "sdrpp_raw_cs16", "qmap_linrad"}:
            raise ValueError("unsupported UDP transport")
        if not 4 <= int(max_datagram_bytes) <= MAX_UDP_DATAGRAM_BYTES:
            raise ValueError("UDP datagram size must be between 4 and 65507 bytes")
        if transport == "sdbu_v2" and max_datagram_bytes <= HEADER_BYTES:
            raise ValueError("SDBU datagram size must exceed its header")
        self.destination = destination
        self.transport = transport
        self.encoder = SDBUEncoder(wire_stream_id, max_datagram_bytes)
        self.qmap_encoder = QMAPEncoder()
        self.max_datagram_bytes = max_datagram_bytes
        self.multicast_interface = multicast_interface
        self.multicast_loopback = multicast_loopback
        self._queue: queue.Queue[IQBlock] = queue.Queue(maxsize=queue_blocks)
        self.queue_blocks = int(queue_blocks)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.sent_packets = 0
        self.sent_bytes = 0
        self.socket_errors = 0
        self.dropped_blocks = 0
        self.last_error: str | None = None
        self.last_center_frequency_hz: int | None = None
        self.last_sample_rate_sps: int | None = None
        # SDR++ consumes the raw UDP stream continuously.  The source/ring
        # side can deliver several blocks in a burst (especially on Windows),
        # so keep a small jitter buffer and release blocks at their RF cadence.
        self._raw_buffer_blocks = max(0, int(raw_buffer_blocks))
        self._raw_next_deadline: float | None = None
        self._raw_rate_sps: int | None = None
        self._raw_prefill_started: float | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name=f"udp-{self.destination[1]}", daemon=True)
        self._thread.start()

    def enqueue(self, block: IQBlock) -> None:
        try:
            self._queue.put_nowait(block)
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                pass
            self.dropped_blocks += 1
            self._queue.put_nowait(block)

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)
            if self._thread.is_alive():
                raise RuntimeError("UDP destination did not stop")
        self._thread = None

    def _raw_packets(self, block: IQBlock) -> list[bytes]:
        if block.sample_format is not SampleFormat.CS16:
            raise ValueError("SDR++ raw profile requires CS16")
        sample_bytes = block.sample_format.bytes_per_iq
        max_samples = self.max_datagram_bytes // sample_bytes
        raw = bytes(block.payload)
        return [raw[i * sample_bytes:(i + max_samples) * sample_bytes] for i in range(0, block.sample_count, max_samples)]

    def _run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        host = self.destination[0]
        is_multicast = 224 <= int(host.split(".")[0]) <= 239 if host.count(".") == 3 else False
        raw_pending = bytearray()
        raw_pending_rate: int | None = None
        raw_bytes_per_iq = SampleFormat.CS16.bytes_per_iq
        raw_payload_limit = self.max_datagram_bytes - (self.max_datagram_bytes % raw_bytes_per_iq)
        if is_multicast:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, int(self.multicast_loopback))
            if self.multicast_interface:
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(self.multicast_interface))
        try:
            while not self._stop.is_set() or not self._queue.empty():
                if (self.transport == "sdrpp_raw_cs16" and self._raw_buffer_blocks
                        and self._raw_next_deadline is None and not self._stop.is_set()):
                    # Pre-fill before the first packet.  Without this, a
                    # transient producer gap becomes an audible underrun in
                    # SDR++ even though no UDP datagram was lost.
                    if self._raw_prefill_started is None:
                        self._raw_prefill_started = time.perf_counter()
                    # A live source can produce exactly as fast as the
                    # consumer, so waiting for a full N-block queue forever
                    # would deadlock the destination. Start after a bounded
                    # prefill window and let the queue absorb later bursts.
                    prefill_elapsed = time.perf_counter() - self._raw_prefill_started
                    if (self._queue.qsize() < self._raw_buffer_blocks
                            and prefill_elapsed < 0.050):
                        time.sleep(0)
                        continue
                try:
                    block = self._queue.get(timeout=0.05)
                except queue.Empty:
                    # Vider un reliquat est nécessaire si le producteur s'est
                    # arrêté entre deux blocs, mais conserver l'échéancier
                    # évite de transformer cette pause en nouvelle rafale au
                    # prochain paquet. Les frontières de flux (débit,
                    # reconfiguration, arrêt) sont traitées séparément.
                    if self.transport == "sdrpp_raw_cs16" and raw_pending:
                        try:
                            sent = sock.sendto(bytes(raw_pending), self.destination)
                            self.sent_packets += 1
                            self.sent_bytes += sent
                        except OSError as exc:
                            self.socket_errors += 1
                            self.last_error = str(exc)
                        raw_pending.clear()
                    continue
                try:
                    self.last_center_frequency_hz = block.center_frequency_hz
                    self.last_sample_rate_sps = block.sample_rate_sps
                    if self.transport == "sdrpp_raw_cs16":
                        if (self._raw_rate_sps != block.sample_rate_sps
                                or block.discontinuity is not Discontinuity.NONE):
                            self._raw_next_deadline = None
                            self._raw_rate_sps = block.sample_rate_sps
                            self._raw_prefill_started = None
                        if (raw_pending and (raw_pending_rate != block.sample_rate_sps
                                or block.discontinuity is not Discontinuity.NONE)):
                            # Never bridge a reconfiguration/epoch boundary
                            # with a headerless raw stream.
                            try:
                                sent = sock.sendto(bytes(raw_pending), self.destination)
                                self.sent_packets += 1
                                self.sent_bytes += sent
                            except OSError as exc:
                                self.socket_errors += 1
                                self.last_error = str(exc)
                            raw_pending.clear()
                        raw_pending_rate = block.sample_rate_sps
                        if self._raw_next_deadline is None:
                            self._raw_next_deadline = time.perf_counter()
                        remaining = self._raw_next_deadline - time.perf_counter()
                        if remaining > 0:
                            # Python 3.12 uses a high-resolution waitable timer
                            # on Windows. Sleeping to the deadline avoids the
                            # CPU-heavy yield loop previously used here.
                            self._stop.wait(remaining)
                    if self.transport == "sdbu_v2":
                        packets = self.encoder.encode(block)
                    elif self.transport == "qmap_linrad":
                        packets = self.qmap_encoder.encode(block)
                    else:
                        raw_pending.extend(bytes(block.payload))
                        packets = []
                        while len(raw_pending) >= raw_payload_limit:
                            packets.append(bytes(raw_pending[:raw_payload_limit]))
                            del raw_pending[:raw_payload_limit]
                    for packet in packets:
                        try:
                            sent = sock.sendto(packet, self.destination)
                            self.sent_packets += 1
                            self.sent_bytes += sent
                        except OSError as exc:
                            self.socket_errors += 1
                            self.last_error = str(exc)
                    if self.transport == "sdrpp_raw_cs16" and self._raw_next_deadline is not None:
                        self._raw_next_deadline += block.sample_count / block.sample_rate_sps
                except Exception as exc:
                    self.socket_errors += 1
                    self.last_error = str(exc)
                finally:
                    self._queue.task_done()
            if raw_pending:
                try:
                    sent = sock.sendto(bytes(raw_pending), self.destination)
                    self.sent_packets += 1
                    self.sent_bytes += sent
                except OSError as exc:
                    self.socket_errors += 1
                    self.last_error = str(exc)
        finally:
            sock.close()

    def snapshot(self) -> dict:
        return {
            "destination": f"{self.destination[0]}:{self.destination[1]}",
            "transport": self.transport,
            "sent_packets": self.sent_packets,
            "sent_bytes": self.sent_bytes,
            "socket_errors": self.socket_errors,
            "dropped_blocks": self.dropped_blocks,
            "last_error": self.last_error,
            "last_center_frequency_hz": self.last_center_frequency_hz,
            "last_sample_rate_sps": self.last_sample_rate_sps,
            "datagram_bytes": QMAP_PACKET_BYTES if self.transport == "qmap_linrad" else self.max_datagram_bytes,
            "queue_blocks": self.queue_blocks,
            "pending_samples": self.qmap_encoder.pending_samples if self.transport == "qmap_linrad" else 0,
            "discarded_samples": self.qmap_encoder.discarded_samples if self.transport == "qmap_linrad" else 0,
        }


class UDPStreamer:
    """Adaptateur historique : lit un ring et émet SDBU v2."""

    def __init__(self, ring, destination: tuple[str, int], mtu: int = DEFAULT_DATAGRAM_BYTES, transport: str = "sdbu_v2"):
        from .ring import RingReader
        self.reader = RingReader(ring)
        # SDR++'s raw source has no application-level MTU.  On loopback a
        # larger datagram is safe and avoids thousands of tiny UDP wakeups per
        # second at 2 MS/s.  Keep the conservative MTU for LAN/multicast,
        # where IP fragmentation would be harmful.
        if (transport == "sdrpp_raw_cs16" and mtu == DEFAULT_DATAGRAM_BYTES
                and destination[0] in {"127.0.0.1", "localhost", "::1"}):
            mtu = LOOPBACK_RAW_DATAGRAM_BYTES
        self.destination = UDPDestination(
            destination, wire_stream_id=1, max_datagram_bytes=mtu,
            transport=transport,
            raw_buffer_blocks=(LOOPBACK_RAW_BUFFER_BLOCKS
                               if transport == "sdrpp_raw_cs16"
                               and destination[0] in {"127.0.0.1", "localhost", "::1"}
                               else 0),
        )
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def sent_packets(self) -> int:
        return self.destination.sent_packets

    def start(self) -> None:
        self.destination.start()
        self._thread = threading.Thread(target=self._run, name="udp-ring-adapter", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        self.destination.stop()

    def _run(self) -> None:
        while not self._stop.is_set():
            block = self.reader.read(.25)
            if block:
                self.destination.enqueue(block)


class QMAPStreamer:
    """Subscribe to the shared 96 kS/s DSP profile and emit Linrad UDP."""

    def __init__(self, bridge, destination: tuple[str, int]):
        self.bridge = bridge
        self.destination = UDPDestination(
            destination,
            wire_stream_id=1,
            transport="qmap_linrad",
        )
        self._profile_token: str | None = None

    @property
    def sent_packets(self) -> int:
        return self.destination.sent_packets

    def start(self) -> None:
        if self._profile_token is not None:
            return
        self.destination.start()
        try:
            self._profile_token, _ = self.bridge.subscribe_profile(
                "qmap-linrad-96k", 1, self.destination.enqueue,
            )
        except Exception:
            self.destination.stop()
            raise

    def stop(self) -> None:
        if self._profile_token is not None:
            self.bridge.unsubscribe_profile(self._profile_token)
            self._profile_token = None
        self.destination.stop()


class ProfileUDPStreamer:
    """Emit one operator destination from a shared immutable DSP profile."""

    LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}

    def __init__(
        self,
        bridge,
        destination: tuple[str, int],
        *,
        transport: str,
        sample_rate_sps: int,
        datagram_bytes: int | None = None,
        queue_blocks: int = 32,
    ):
        if transport == "qmap_linrad":
            if int(sample_rate_sps) != QMAP_SAMPLE_RATE_SPS:
                raise ValueError("QMAP/Linrad rate is fixed at 96000 S/s")
            datagram_bytes = QMAP_PACKET_BYTES
        elif datagram_bytes is None:
            datagram_bytes = LOOPBACK_RAW_DATAGRAM_BYTES if destination[0] in self.LOOPBACK_HOSTS else DEFAULT_DATAGRAM_BYTES
        self.bridge = bridge
        self.transport = transport
        self.sample_rate_sps = int(sample_rate_sps)
        self.profile = StreamProfile(
            f"udp-cs16-{self.sample_rate_sps}",
            1,
            self.sample_rate_sps,
            SampleFormat.CS16,
            transport,
            name=f"UDP CS16 {self.sample_rate_sps} S/s",
        )
        source_block_seconds = bridge.ring.block_samples / bridge.config.sample_rate_sps
        raw_buffer_blocks = max(2, min(8, math.ceil(0.016 / source_block_seconds)))
        self.destination = UDPDestination(
            destination,
            wire_stream_id=1,
            transport=transport,
            max_datagram_bytes=int(datagram_bytes),
            queue_blocks=int(queue_blocks),
            raw_buffer_blocks=(
                raw_buffer_blocks
                if transport == "sdrpp_raw_cs16" and destination[0] in self.LOOPBACK_HOSTS
                else 0
            ),
        )
        self._profile_token: str | None = None

    @property
    def sent_packets(self) -> int:
        return self.destination.sent_packets

    def start(self) -> None:
        if self._profile_token is not None:
            return
        self.destination.start()
        try:
            self._profile_token, _ = self.bridge.subscribe_stream_profile(self.profile, self.destination.enqueue)
        except Exception:
            self.destination.stop()
            raise

    def stop(self) -> None:
        if self._profile_token is not None:
            self.bridge.unsubscribe_profile(self._profile_token)
            self._profile_token = None
        self.destination.stop()

    def snapshot(self) -> dict:
        return {
            **self.destination.snapshot(),
            "profile_id": self.profile.profile_id,
            "configured_sample_rate_sps": self.sample_rate_sps,
        }
