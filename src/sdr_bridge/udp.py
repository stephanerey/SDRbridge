from __future__ import annotations

from dataclasses import dataclass
import queue
import socket
import struct
import threading

from .model import Discontinuity, IQBlock, SampleFormat, TimeDomain, TimestampOrigin

HEADER = struct.Struct(">4sBBHHBBIQQQQIIQII")
MAGIC = b"SDBU"
VERSION = 2
HEADER_BYTES = 72
DEFAULT_DATAGRAM_BYTES = 1200

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
        multicast_interface: str | None = None,
        multicast_loopback: bool = False,
    ):
        if transport not in {"sdbu_v2", "sdrpp_raw_cs16"}:
            raise ValueError("unsupported UDP transport")
        self.destination = destination
        self.transport = transport
        self.encoder = SDBUEncoder(wire_stream_id, max_datagram_bytes)
        self.max_datagram_bytes = max_datagram_bytes
        self.multicast_interface = multicast_interface
        self.multicast_loopback = multicast_loopback
        self._queue: queue.Queue[IQBlock] = queue.Queue(maxsize=queue_blocks)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.sent_packets = 0
        self.sent_bytes = 0
        self.socket_errors = 0
        self.dropped_blocks = 0
        self.last_error: str | None = None
        self.last_center_frequency_hz: int | None = None
        self.last_sample_rate_sps: int | None = None

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
        if is_multicast:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, int(self.multicast_loopback))
            if self.multicast_interface:
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(self.multicast_interface))
        try:
            while not self._stop.is_set() or not self._queue.empty():
                try:
                    block = self._queue.get(timeout=0.05)
                except queue.Empty:
                    continue
                try:
                    self.last_center_frequency_hz = block.center_frequency_hz
                    self.last_sample_rate_sps = block.sample_rate_sps
                    packets = self.encoder.encode(block) if self.transport == "sdbu_v2" else self._raw_packets(block)
                    for packet in packets:
                        try:
                            sent = sock.sendto(packet, self.destination)
                            self.sent_packets += 1
                            self.sent_bytes += sent
                        except OSError as exc:
                            self.socket_errors += 1
                            self.last_error = str(exc)
                except Exception as exc:
                    self.socket_errors += 1
                    self.last_error = str(exc)
                finally:
                    self._queue.task_done()
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
        }


class UDPStreamer:
    """Adaptateur historique : lit un ring et émet SDBU v2."""

    def __init__(self, ring, destination: tuple[str, int], mtu: int = DEFAULT_DATAGRAM_BYTES, transport: str = "sdbu_v2"):
        from .ring import RingReader
        self.reader = RingReader(ring)
        self.destination = UDPDestination(destination, wire_stream_id=1, max_datagram_bytes=mtu, transport=transport)
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
