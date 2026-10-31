import json
import socket
import time
import unittest

import numpy as np

from sdr_bridge.bridge import SDRBridge
from sdr_bridge.model import Discontinuity, IQBlock, SampleFormat, TimeDomain, TimestampOrigin
from sdr_bridge.native_control import NativeControlServer
from sdr_bridge.source import SimulatedSource
from sdr_bridge.udp import (
    HEADER_BYTES,
    FLAG_DISCONTINUITY,
    FLAG_TIME_VALID,
    QMAPEncoder,
    QMAP_PACKET_BYTES,
    SDBUEncoder,
    UDPDestination,
    parse_datagram,
    parse_qmap_datagram,
)


def _block(sample_format=SampleFormat.CS16, count=400, *, rate=192_000, discontinuity=Discontinuity.START):
    if sample_format is SampleFormat.CS16:
        payload = np.arange(count * 2, dtype="<i2").tobytes()
    else:
        payload = (np.arange(count, dtype=np.float32) + 1j * np.arange(count, dtype=np.float32)).astype("<c8").tobytes()
    return IQBlock(
        "source-0", 3, 9, 5, count, rate, 144_300_000, 7, sample_format,
        6, TimeDomain.HOST_MONOTONIC, TimestampOrigin.HOST_OBSERVATION,
        discontinuity, 0, memoryview(payload),
    )


class UDPProtocolTests(unittest.TestCase):
    def test_header_exact_vector_and_round_trip(self):
        packet = SDBUEncoder(42).encode(_block(count=2))[0]
        expected = b"".join((
            b"SDBU", b"\x02", b"\x01", (FLAG_TIME_VALID | FLAG_DISCONTINUITY).to_bytes(2, "big"),
            (72).to_bytes(2, "big"), b"\x02", b"\x00", (42).to_bytes(4, "big"),
            (3).to_bytes(8, "big"), (0).to_bytes(8, "big"), (5).to_bytes(8, "big"),
            (6).to_bytes(8, "big"), (7).to_bytes(4, "big"), (192_000).to_bytes(4, "big"),
            (144_300_000).to_bytes(8, "big"), (2).to_bytes(4, "big"), (0).to_bytes(4, "big"),
        ))
        self.assertEqual(packet[:HEADER_BYTES], expected)
        decoded = parse_datagram(packet)
        self.assertEqual(decoded.wire_stream_id, 42)
        self.assertEqual(decoded.first_sample_index, 5)
        self.assertEqual(decoded.payload, bytes(_block(count=2).payload))

    def test_packet_budget_and_parser_rejections(self):
        for fmt, maximum in ((SampleFormat.CS16, 282), (SampleFormat.CF32, 141)):
            packets = SDBUEncoder(1).encode(_block(fmt, 400))
            self.assertTrue(all(len(item) <= 1200 for item in packets))
            self.assertTrue(all(parse_datagram(item).sample_count <= maximum for item in packets))
        valid = bytearray(SDBUEncoder(1).encode(_block(count=2))[0])
        valid[11] = 1
        with self.assertRaises(ValueError):
            parse_datagram(bytes(valid))
        with self.assertRaises(ValueError):
            parse_datagram(b"short")

    def test_sdrpp_raw_is_headerless_and_sample_aligned(self):
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(("127.0.0.1", 0)); receiver.settimeout(2)
        destination = UDPDestination(receiver.getsockname(), wire_stream_id=2, transport="sdrpp_raw_cs16")
        destination.start()
        try:
            destination.enqueue(_block(count=700))
            received = []
            while sum(len(item) for item in received) < 700 * 4:
                received.append(receiver.recvfrom(2000)[0])
            self.assertTrue(all(len(item) <= 1200 and len(item) % 4 == 0 for item in received))
            self.assertFalse(received[0].startswith(b"SDBU"))
        finally:
            destination.stop(); receiver.close()

    def test_qmap_linrad_exact_layout_transform_and_aggregation(self):
        encoder = QMAPEncoder(clock_ms=lambda: 12_345)
        first = encoder.encode(_block(count=400, rate=96_000))
        self.assertEqual(len(first), 1)
        self.assertEqual(len(first[0]), QMAP_PACKET_BYTES)
        decoded = parse_qmap_datagram(first[0])
        self.assertAlmostEqual(decoded.center_frequency_mhz, 144.3)
        self.assertEqual(decoded.milliseconds, 12_345)
        self.assertEqual(decoded.block_sequence, 0)
        self.assertEqual(decoded.receiver_count, 1)
        original = np.arange(400 * 2, dtype=np.int16).reshape(-1, 2)[:348].astype(np.int32)
        sign = 1 - 2 * (np.arange(348) & 1)
        expected = original.copy()
        expected[:, 0] *= sign
        expected[:, 1] *= -sign
        actual = np.frombuffer(decoded.payload, dtype="<i2").reshape(-1, 2)
        np.testing.assert_array_equal(actual, expected.astype(np.int16))

        second = encoder.encode(_block(count=296, rate=96_000, discontinuity=Discontinuity.NONE))
        self.assertEqual(len(second), 1)
        self.assertEqual(parse_qmap_datagram(second[0]).block_sequence, 1)
        self.assertEqual(encoder.pending_samples, 0)

    def test_qmap_rejects_wrong_rate_and_resets_partial_packet(self):
        encoder = QMAPEncoder(clock_ms=lambda: 0)
        with self.assertRaisesRegex(ValueError, "96000"):
            encoder.encode(_block(count=348))
        self.assertEqual(encoder.encode(_block(count=100, rate=96_000)), [])
        reset = _block(count=348, rate=96_000, discontinuity=Discontinuity.SOURCE_LOSS)
        self.assertEqual(len(encoder.encode(reset)), 1)
        self.assertEqual(encoder.discarded_samples, 100)
        with self.assertRaises(ValueError):
            parse_qmap_datagram(b"short")


class NativeControlTests(unittest.TestCase):
    def setUp(self):
        self.bridge = SDRBridge(SimulatedSource(), block_samples=4096)
        self.bridge.start()
        self.server = NativeControlServer(self.bridge, port=0)
        self.server.start()
        self.sock = socket.create_connection(self.server.address, timeout=2)
        self.stream = self.sock.makefile("rwb")
        self.counter = 0

    def tearDown(self):
        self.stream.close(); self.sock.close()
        self.server.close(); self.bridge.close()

    def request(self, method, params, *, version=1):
        self.counter += 1
        request = {"api_version": version, "request_id": str(self.counter), "method": method, "params": params}
        self.stream.write(json.dumps(request).encode() + b"\n"); self.stream.flush()
        return json.loads(self.stream.readline())

    def hello(self):
        response = self.request("hello", {"client_name": "test", "client_version": "1"})
        self.assertTrue(response["ok"])
        return response

    def test_hello_two_unicast_and_no_rf_control(self):
        self.hello()
        receivers = []
        subscriptions = []
        try:
            for _ in range(2):
                receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                receiver.bind(("127.0.0.1", 0)); receiver.settimeout(4)
                receivers.append(receiver)
                response = self.request("subscribe", {
                    "source_id": "source-0", "profile_id": "native-cs16-192k", "profile_revision": 1,
                    "transport": "udp_unicast", "port": receiver.getsockname()[1],
                })
                self.assertTrue(response["ok"])
                self.assertEqual(response["result"]["endpoint"]["host"], "127.0.0.1")
                subscriptions.append(response["result"]["subscription_id"])
            for receiver in receivers:
                packet = parse_datagram(receiver.recvfrom(2000)[0])
                self.assertEqual(packet.sample_rate_sps, 192_000)
            denied = self.request("set_config", {"center_frequency_hz": 1})
            self.assertFalse(denied["ok"])
            for sub in subscriptions:
                first = self.request("unsubscribe", {"subscription_id": sub})
                second = self.request("unsubscribe", {"subscription_id": sub})
                self.assertFalse(first["result"]["already_closed"])
                self.assertTrue(second["result"]["already_closed"])
        finally:
            for receiver in receivers:
                receiver.close()

    def test_invalid_version_duplicate_keys_and_token(self):
        wrong = self.request("hello", {"client_name": "test", "client_version": "1"}, version=2)
        self.assertEqual(wrong["error"]["code"], "UNSUPPORTED_VERSION")
        self.stream.write(b'{"api_version":1,"api_version":1,"request_id":"x","method":"hello","params":{}}\n'); self.stream.flush()
        duplicate = json.loads(self.stream.readline())
        self.assertEqual(duplicate["error"]["code"], "BAD_REQUEST")

    def test_line_limit_closes_connection(self):
        extra = socket.create_connection(self.server.address, timeout=2)
        extra.sendall(b"{" + b" " * 65_536 + b"\n")
        extra.settimeout(2)
        self.assertEqual(extra.recv(1), b"")
        extra.close()

    def test_token_not_echoed(self):
        server = NativeControlServer(self.bridge, port=0, token="x" * 32)
        server.start()
        sock = socket.create_connection(server.address, timeout=2)
        stream = sock.makefile("rwb")
        try:
            request = {"api_version": 1, "request_id": "secret-test", "method": "hello", "params": {"client_name": "x", "client_version": "1"}}
            stream.write(json.dumps(request).encode() + b"\n"); stream.flush()
            raw = stream.readline()
            self.assertNotIn(("x" * 32).encode(), raw)
            self.assertEqual(json.loads(raw)["error"]["code"], "UNAUTHORIZED")
        finally:
            stream.close(); sock.close(); server.close()


if __name__ == "__main__":
    unittest.main()
