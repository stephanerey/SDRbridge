import json
import socket
import tempfile
import time
import unittest
from copy import deepcopy
from pathlib import Path

from sdr_bridge.bridge import SDRBridge
from sdr_bridge.app import AppRuntime
from sdr_bridge.config import DEFAULT_CONFIG, load_app_config, save_app_config
from sdr_bridge.control import ControlServer
from sdr_bridge.model import RadioConfig
from sdr_bridge.ring import RingReader, SharedIQRing
from sdr_bridge.source import SimulatedSource
from sdr_bridge.udp import parse_datagram, parse_qmap_datagram


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

    def test_read_latest_skips_history_without_draining(self):
        ring = SharedIQRing(8, 8)
        try:
            reader = RingReader(ring, start_at_latest=False)
            payload = memoryview(bytes(range(32)))
            for seq in range(6):
                ring.write(seq, 100 + seq, 2, 8, payload)
            block = reader.read_latest(0.1)
            self.assertIsNotNone(block)
            self.assertEqual(block.sequence, 5)
            self.assertEqual(reader.dropped_blocks, 5)
            self.assertIsNone(reader.read_latest(0.001))
        finally:
            ring.close(unlink=True)


class BridgeTests(unittest.TestCase):
    def test_lan_udp_permission_is_separate_persistent_and_immediate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "app.json"
            config = deepcopy(DEFAULT_CONFIG)
            config["source"] = "simulated"
            config["network"]["legacy_control_port"] = 0
            config["network"]["control_port"] = 0
            save_app_config(path, config)
            runtime = AppRuntime(config, config_path=path)
            try:
                with self.assertRaisesRegex(ValueError, "Allow LAN UDP destinations"):
                    runtime._build_udp_streamer("192.0.2.10:7356", "sdbu_v2", 192_000, 1200, 32)
                self.assertTrue(runtime.set_lan_udp_enabled(True))
                self.assertFalse(runtime.config["network"]["enabled"])
                self.assertTrue(load_app_config(path)[1]["network"]["allow_lan_udp"])
                _, streamer = runtime._build_udp_streamer(
                    "192.0.2.10:7356", "sdbu_v2", 192_000, 1200, 32,
                )
                streamer.stop()
            finally:
                runtime.close()

    def test_gui_runtime_can_start_disconnected_for_device_discovery(self):
        config = deepcopy(DEFAULT_CONFIG)
        config["source"] = "simulated"
        config["network"] = deepcopy(DEFAULT_CONFIG["network"])
        config["network"]["legacy_control_port"] = 0
        config["network"]["control_port"] = 0
        runtime = AppRuntime(config)
        runtime.bridge.source.enumerate = lambda: []
        try:
            runtime.start(start_rx=False)
            self.assertEqual(runtime.bridge.state.value, "IDLE")
            self.assertFalse(runtime.bridge.running)
        finally:
            runtime.close()

    def test_three_udp_destinations_have_effective_independent_rates(self):
        config = deepcopy(DEFAULT_CONFIG)
        config["network"] = deepcopy(DEFAULT_CONFIG["network"])
        config["network"]["legacy_control_port"] = 0
        config["network"]["control_port"] = 0
        config["radio"] = deepcopy(DEFAULT_CONFIG["radio"])
        config["radio"]["sample_rate_sps"] = 2_000_000
        config["source"] = "simulated"
        receivers = []
        runtime = AppRuntime(config)
        try:
            runtime.start(start_rx=True)
            expected_rates = (2_000_000, 192_000, 1_000_000)
            endpoints = []
            for rate in expected_rates:
                receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                receiver.bind(("127.0.0.1", 0))
                receiver.settimeout(4)
                receivers.append(receiver)
                endpoint = f"127.0.0.1:{receiver.getsockname()[1]}"
                endpoints.append(endpoint)
                runtime.add_udp_destination(endpoint, "sdbu_v2", rate)

            decoded = [parse_datagram(receiver.recvfrom(9000)[0]) for receiver in receivers]
            self.assertEqual(tuple(item.sample_rate_sps for item in decoded), expected_rates)
            snapshots = runtime.udp_destinations_snapshot()
            self.assertEqual(tuple(item["configured_sample_rate_sps"] for item in snapshots), expected_rates)
            self.assertTrue(all(item["datagram_bytes"] == 8192 for item in snapshots))
            self.assertTrue(all(len(item.payload) + 72 <= 8192 for item in decoded))
            self.assertEqual(len(runtime.bridge.status()["pipelines"]), 3)

            runtime.update_udp_destination(endpoints[1], "sdbu_v2", 1_000_000, 1200, 64)
            updated = runtime.udp_destinations_snapshot()[1]
            self.assertEqual(updated["configured_sample_rate_sps"], 1_000_000)
            self.assertEqual(updated["datagram_bytes"], 1200)
            self.assertEqual(updated["queue_blocks"], 64)
            self.assertEqual(len(runtime.bridge.status()["pipelines"]), 2)
        finally:
            runtime.close()
            for receiver in receivers:
                receiver.close()

    def test_runtime_supports_multiple_udp_destinations(self):
        config = deepcopy(DEFAULT_CONFIG)
        config["network"] = deepcopy(DEFAULT_CONFIG["network"])
        config["network"]["legacy_control_port"] = 0
        config["network"]["control_port"] = 0
        config["radio"] = deepcopy(DEFAULT_CONFIG["radio"])
        config["source"] = "simulated"
        runtime = AppRuntime(config)
        qmap_receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        qmap_receiver.bind(("127.0.0.1", 0))
        qmap_receiver.settimeout(3)
        try:
            runtime.start(start_rx=True)
            runtime.add_udp_destination("127.0.0.1:7356", "sdrpp_raw_cs16")
            qmap_endpoint = f"127.0.0.1:{qmap_receiver.getsockname()[1]}"
            runtime.add_udp_destination(qmap_endpoint, "qmap_linrad")
            packet = qmap_receiver.recvfrom(2000)[0]
            decoded = parse_qmap_datagram(packet)
            self.assertAlmostEqual(decoded.center_frequency_mhz, 144.3)
            snapshots = runtime.udp_destinations_snapshot()
            self.assertEqual([item["transport"] for item in snapshots], ["sdrpp_raw_cs16", "qmap_linrad"])
            self.assertEqual(snapshots[1]["last_sample_rate_sps"], 96_000)
            runtime.remove_udp_destination("127.0.0.1:7356")
            self.assertEqual([item["destination"] for item in runtime.udp_destinations_snapshot()], [qmap_endpoint])
        finally:
            runtime.close()
            qmap_receiver.close()

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

