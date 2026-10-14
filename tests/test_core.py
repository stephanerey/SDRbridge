import json
import socket
import time
import unittest

from sdr_bridge.bridge import SDRBridge
from sdr_bridge.control import ControlServer
from sdr_bridge.model import RadioConfig
from sdr_bridge.ring import RingReader, SharedIQRing
from sdr_bridge.source import SimulatedSource


class RingTests(unittest.TestCase):
    def test_write_read_and_overrun(self):
        ring = SharedIQRing(4, 8)
        try:
            reader = RingReader(ring, start_at_latest=False)
            payload = memoryview(bytes(range(32)))
            for seq in range(6):
                ring.write(seq, 100 + seq, 2, 8, payload)
            block = reader.read(0.1)
            self.assertIsNotNone(block)
            self.assertEqual(block.sequence, 2)
            self.assertEqual(reader.dropped_blocks, 2)
            self.assertEqual(bytes(block.payload), bytes(payload))
        finally:
            ring.close(unlink=True)


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.bridge = SDRBridge(SimulatedSource(block_samples=2048), RadioConfig(), block_samples=2048, slots=16)
        self.bridge.start()

    def tearDown(self):
        self.bridge.close()

    def test_five_clients_and_server_only_configuration(self):
        clients = [self.bridge.register_client(f"client-{i}") for i in range(5)]
        for client_id, reader in clients:
            block = reader.read(1.0)
            self.assertIsNotNone(block)
            self.assertEqual(block.sample_count, 2048)
            self.bridge.record_read(client_id, block.sequence, block.sample_count, reader.dropped_blocks)
        config = self.bridge.set_config(center_frequency_hz=144_350_000)
        self.assertEqual(config.center_frequency_hz, 144_350_000)
        self.assertEqual(config.revision, 2)

    def test_loopback_control_and_external_reader(self):
        control = ControlServer(self.bridge, port=0)
        control.start()
        sock = socket.create_connection(control.address, timeout=2)
        stream = sock.makefile("rwb")
        try:
            stream.write(b'{"action":"register","name":"test-adapter"}\n'); stream.flush()
            response = json.loads(stream.readline())
            self.assertTrue(response["ok"])
            desc = response["ring"]
            attached = SharedIQRing.attach(desc)
            try:
                block = RingReader(attached).read(1.0)
                self.assertIsNotNone(block)
            finally:
                attached.close()
            stream.write(b'{"action":"set_config","changes":{"center_frequency_hz":145000000}}\n'); stream.flush()
            denied = json.loads(stream.readline())
            self.assertFalse(denied["ok"])
        finally:
            stream.close(); sock.close(); control.close()


if __name__ == "__main__":
    unittest.main()

