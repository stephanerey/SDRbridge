import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time
import unittest

from PyQt5 import QtTest, QtWidgets

from sdr_bridge.bridge import SDRBridge
from sdr_bridge.gui import BridgeWindow
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
            "Radio", "Sorties et clients", "Profils RF", "Captures", "Diagnostics",
        ])
        clients = [self.bridge.register_client(f"client-{index}") for index in range(5)]
        try:
            self.window.refresh()
            self.assertGreaterEqual(self.window.clients_table.rowCount(), 6)  # cinq + spectre GUI
            self.window.frequency_edit.setText("invalide")
            self.window._apply_config()
            self.assertTrue(self.window.error_banner.isVisible())
            self.assertIn("Configuration refusée", self.window.error_banner.text())
            self.assertIn("Effectif", self.window.effective_label.text())
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
        self.assertIn("SIMULATION", self.window.connection_label.text())
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


if __name__ == "__main__":
    unittest.main()
