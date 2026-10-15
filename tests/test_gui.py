import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time
import unittest

import numpy as np

from PyQt5 import QtTest, QtWidgets

from sdr_bridge.bridge import SDRBridge
from sdr_bridge.gui import BridgeWindow, SpectrumService
from sdr_bridge.model import DeviceDescriptor, RadioConfig
from sdr_bridge.native_sdrplay import NativeSDRplaySource
from sdr_bridge.source import SimulatedSource


class QtInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        self.bridge = SDRBridge(SimulatedSource(block_samples=512), block_samples=512, slots=16)
        self.bridge.start()
        self.window = BridgeWindow(self.bridge)
        self.window.show()
        QtTest.QTest.qWait(80)

    def tearDown(self):
        if not self.bridge._closed:
            self.bridge.stop()
        self.window.close()
        QtWidgets.QApplication.processEvents()

    def test_normal_compact_100_times_preserves_stream_and_fft_service(self):
        service = self.window.spectrum
        epoch = self.bridge.epoch
        before = self.bridge.blocks_written
        for _ in range(100):
            self.window.toggle_compact()
            self.window.toggle_compact()
        QtTest.QTest.qWait(100)
        self.assertIs(self.window.spectrum, service)
        self.assertEqual(self.bridge.epoch, epoch)
        self.assertTrue(self.bridge.running)
        self.assertGreater(self.bridge.blocks_written, before)
        self.assertEqual(self.window._stack.currentIndex(), 0)

    def test_tabs_effective_state_invalid_draft_and_five_clients(self):
        self.assertEqual([self.window.tabs.tabText(i) for i in range(self.window.tabs.count())], [
            "Radio", "Outputs & Clients", "RF Profiles", "Captures", "Diagnostics",
        ])
        clients = [self.bridge.register_client(f"client-{index}") for index in range(5)]
        try:
            self.window.refresh()
            self.assertGreaterEqual(self.window.clients_table.rowCount(), 6)  # cinq + spectre GUI
            self.window.frequency_edit.setText("invalide")
            self.window._apply_config()
            self.assertTrue(self.window.error_banner.isVisible())
            self.assertIn("Configuration rejected", self.window.error_banner.text())
            self.assertFalse(hasattr(self.window, "effective_label"))
        finally:
            for client_id, _ in clients:
                self.bridge.unregister_client(client_id)

    def test_compact_contract_dimensions_and_text_state(self):
        self.window.toggle_compact()
        QtWidgets.QApplication.processEvents()
        self.assertGreaterEqual(self.window.minimumWidth(), 360)
        self.assertGreaterEqual(self.window.minimumHeight(), 100)
        self.assertIn("RUNNING", self.window.compact_state.text())
        self.assertIn("Hz", self.window.compact_frequency.text())

    def test_simulation_indicator_and_adjustable_relative_db_scale(self):
        self.window.refresh()
        self.assertIn("Simulation", self.window.connection_label.text())
        self.window.y_min_spin.setValue(-130)
        self.window.y_max_spin.setValue(10)
        self.assertEqual(self.window.normal_plot.getViewBox().viewRange()[1], [-130.0, 10.0])

    def test_frequency_edit_is_applied_without_button_and_keeps_rx_running(self):
        before_epoch = self.bridge.epoch
        started = time.perf_counter()
        self.window.frequency_edit.setText("145000000")
        self.window.frequency_edit.editingFinished.emit()
        deadline = time.perf_counter() + 0.8
        while time.perf_counter() < deadline:
            QtTest.QTest.qWait(20)
            if self.bridge.config.center_frequency_hz == 145_000_000 and not self.window._config_apply_busy:
                break
        self.assertEqual(self.bridge.config.center_frequency_hz, 145_000_000)
        self.assertTrue(self.bridge.running)
        self.assertGreater(self.bridge.blocks_written, 0)
        self.assertGreater(self.bridge.epoch, before_epoch)
        self.assertLess(time.perf_counter() - started, 0.8)

    def test_sampling_rates_and_bandwidth_options_follow_hardware_rate(self):
        native = object.__new__(NativeSDRplaySource)
        self.assertEqual(native.capabilities(native.DEVICE_ID).sample_rates_sps, (2_000_000, 6_000_000, 8_000_000, 10_000_000))
        self.window._capabilities = {
            "bandwidths_hz": (200_000, 300_000, 600_000, 1_536_000, 5_000_000, 6_000_000, 7_000_000, 8_000_000),
        }
        self.window._refresh_bandwidth_combo(2_000_000, 1_536_000)
        self.assertEqual(
            [self.window.bandwidth_combo.itemData(i) for i in range(self.window.bandwidth_combo.count())],
            [200_000, 300_000, 600_000, 1_536_000],
        )
        self.window._refresh_bandwidth_combo(10_000_000, 1_536_000)
        self.assertEqual(self.window.bandwidth_combo.count(), 8)

    def test_source_dropdown_shows_backend_model_and_serial(self):
        self.bridge.source.enumerate = lambda: [
            DeviceDescriptor("simulated:0", "simulated", "Simulation", "seed-1"),
            DeviceDescriptor("soapy:sdrplay:2001077942", "soapy/sdrplay", "RSPdx", "2001077942"),
            DeviceDescriptor("soapy:sdrplay:0000000001", "soapy/sdrplay", "RSP1", "0000000001"),
        ]
        self.window._refresh_devices()
        labels = [self.window.device_combo.itemText(i) for i in range(self.window.device_combo.count())]
        self.assertIn("soapy/sdrplay: RSPdx — S/N 2001077942", labels)
        self.assertIn("soapy/sdrplay: RSP1 — S/N 0000000001", labels)

    def test_antrack_style_digit_frequency_control_changes_one_digit(self):
        self.window.frequency_control.set_value_hz(144_300_000)
        values = []
        self.window.frequency_control.valueChanged.connect(values.append)
        self.window.frequency_control._apply_delta(1_000)
        self.assertEqual(self.window.frequency_control.value_hz(), 144_301_000)
        self.assertEqual(values[-1], 144_301_000)
        self.assertFalse(hasattr(self.window, "apply_button"))

    def test_spectrum_uses_fixed_dbfs_reference(self):
        t = np.arange(4096, dtype=np.float32)
        tone = np.exp(2j * np.pi * 37 * t / len(t))
        quiet = SpectrumService.compute_dbfs(0.1 * tone)
        loud = SpectrumService.compute_dbfs(0.2 * tone)
        peak = int(np.argmax(quiet))
        self.assertAlmostEqual(float(loud[peak] - quiet[peak]), 20 * np.log10(2), places=2)

    def test_spectrum_poll_does_not_starve_at_multi_msps(self):
        source = SimulatedSource(block_samples=4096, realtime=True)
        bridge = SDRBridge(
            source,
            RadioConfig(sample_rate_sps=8_000_000, bandwidth_hz=8_000_000),
            block_samples=4096,
            slots=64,
        )
        bridge.start()
        service = SpectrumService(bridge)
        try:
            deadline = time.perf_counter() + 0.35
            calls = 0
            while time.perf_counter() < deadline:
                started = time.perf_counter()
                service._poll()
                self.assertLess(time.perf_counter() - started, 0.05)
                calls += 1
                time.sleep(0.005)
            self.assertGreater(calls, 20)
            self.assertGreater(service.fft_count, 5)
            self.assertGreater(bridge.blocks_written, 100)
        finally:
            service.close()
            bridge.close()

    def test_toolbar_uses_icons_and_discreet_connection_indicator(self):
        self.assertIsInstance(self.window.start_button, QtWidgets.QToolButton)
        self.assertFalse(self.window.start_button.icon().isNull())
        self.assertIsInstance(self.window.compact_button, QtWidgets.QToolButton)
        self.assertIn("Connected", self.window.state_label.text())
        self.assertNotIn("SDRplay direct API", self.window.windowTitle())


if __name__ == "__main__":
    unittest.main()
