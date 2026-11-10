import os
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import threading
import time
import unittest
from unittest import mock

import numpy as np

from PyQt5 import QtCore, QtGui, QtTest, QtWidgets

from sdr_bridge.bridge import SDRBridge
from sdr_bridge.gui import AbsoluteFrequencyAxis, BridgeWindow, SpectrumService, prepare_gui
from sdr_bridge.gui_theme import DARK_STYLESHEET, SDRBridgeProxyStyle
from sdr_bridge.model import DeviceDescriptor, RadioConfig
from sdr_bridge.native_sdrplay import NativeSDRplaySource
from sdr_bridge.recording import CaptureFormat
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

    def test_application_icon_is_loaded_for_windows_and_taskbar_surfaces(self):
        application = prepare_gui()
        self.assertEqual(application.applicationName(), "SDRbridge")
        self.assertFalse(application.windowIcon().isNull())

    def test_dark_controls_have_visible_unchecked_boxes_and_cyan_arrows(self):
        self.assertIn("QCheckBox::indicator:unchecked", DARK_STYLESHEET)
        self.assertIn("border: 1px solid #6f91a8", DARK_STYLESHEET)
        style = SDRBridgeProxyStyle()
        image = QtGui.QImage(24, 24, QtGui.QImage.Format_ARGB32)
        image.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(image)
        option = QtWidgets.QStyleOption()
        option.rect = QtCore.QRect(0, 0, 24, 24)
        option.state = QtWidgets.QStyle.State_Enabled
        style.drawPrimitive(QtWidgets.QStyle.PE_IndicatorArrowDown, option, painter)
        painter.end()
        cyan_pixels = 0
        for y in range(image.height()):
            for x in range(image.width()):
                color = image.pixelColor(x, y)
                if color.green() > 170 and color.blue() > 180 and color.red() < 100:
                    cyan_pixels += 1
        self.assertGreater(cyan_pixels, 10)

    def test_lan_destination_switches_loopback_datagram_default_to_1200(self):
        self.window.destination_edit.setText("192.0.2.10:7356")
        self.window.destination_datagram.setValue(8192)
        self.window._destination_endpoint_changed()
        self.assertEqual(self.window.destination_datagram.value(), 1200)

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

    def test_four_operator_tabs_effective_state_invalid_draft_and_five_clients(self):
        self.assertEqual([self.window.tabs.tabText(i) for i in range(self.window.tabs.count())], [
            "Radio", "Clients & Streams", "RF Profiles", "Captures",
        ])
        self.assertTrue(hasattr(self.window, "diagnostics_dialog"))
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

    def test_language_switch_retranslates_every_visible_surface_immediately(self):
        self.window.language = "fr"
        self.window._retranslate_ui()

        self.assertEqual([self.window.tabs.tabText(i) for i in range(self.window.tabs.count())], [
            "Radio", "Clients et flux", "Profils RF", "Captures",
        ])
        self.assertEqual(self.window.rate_metric_title.text(), "Débit mesuré")
        self.assertEqual(self.window.loss_metric_title.text(), "Pertes totales")
        self.assertEqual(self.window.cpu_metric_title.text(), "CPU SDRbridge")
        self.assertEqual(self.window.frequency_title.text(), "FRÉQUENCE CENTRALE SDR")
        self.assertEqual(self.window.receiver_group.title(), "RÉCEPTEUR · RÉGLAGES MATÉRIELS")
        self.assertEqual(self.window.rate_label.text(), "Débit d'échantillonnage")
        self.assertEqual(self.window.bandwidth_label.text(), "Bande passante")
        self.assertEqual(self.window.mode_spectrum.text(), "Spectre")
        self.assertEqual(self.window.mode_split.text(), "Partagé")
        self.assertEqual(self.window.smoothing_label.text(), "Lissage")
        self.assertEqual(self.window.normal_plot.getAxis("bottom").labelText, "Fréquence (MHz)")
        self.assertEqual(self.window.waterfall_plot.getAxis("left").labelText, "Historique")
        self.assertEqual(self.window.consumer_table.horizontalHeaderItem(0).text(), "Consommateur / destination")
        self.assertEqual(self.window.destination_editor.title(), "ÉDITEUR DE FLUX UDP")
        self.assertEqual(self.window.edit_rf_rule_button.text(), "Modifier")
        self.assertEqual(self.window.rf_rules_table.horizontalHeaderItem(3).text(), "Priorité")
        self.assertEqual(self.window.capture_group.title(), "CONFIGURATION DE L'ENREGISTREMENT")
        self.assertEqual(self.window.capture_button.text(), "Choisir le fichier et démarrer…")
        self.assertEqual(self.window.diagnostics_title.text(), "DIAGNOSTICS SYSTÈME")
        self.assertIn("consommateur", self.window.compact_consumers.text())
        self.assertIn("pertes de traitement", self.window.status_bar.text())

        self.window.language = "en"
        self.window._retranslate_ui()
        self.assertEqual(self.window.loss_metric_title.text(), "Total losses")
        self.assertEqual(self.window.cpu_metric_title.text(), "SDRbridge CPU")
        self.assertEqual(self.window.tabs.tabText(1), "Clients & Streams")
        self.assertEqual(self.window.frequency_title.text(), "SDR CENTER FREQUENCY")
        self.assertEqual(self.window.smoothing_label.text(), "Smoothing")
        self.assertEqual(self.window.consumer_table.horizontalHeaderItem(0).text(), "Consumer / destination")
        self.assertEqual(self.window.capture_group.title(), "RECORDING CONFIGURATION")
        self.assertIn("processing drops", self.window.status_bar.text())

    def test_normal_rf_axes_show_rounded_absolute_mhz_and_follow_effective_vfo(self):
        axes = [
            self.window.normal_plot.getAxis("bottom"),
            self.window.waterfall_plot.getAxis("bottom"),
            self.window.split_spectrum_plot.getAxis("bottom"),
            self.window.split_waterfall_plot.getAxis("bottom"),
        ]
        self.assertTrue(all(isinstance(axis, AbsoluteFrequencyAxis) for axis in axes))
        self.window._update_frequency_axes(144_735_000)
        for axis in axes:
            self.assertEqual(axis.tickStrings([-0.0025, 0.0, 0.0025], 1.0, 0.0025), [
                "144.7325", "144.7350", "144.7375",
            ])
            self.assertEqual(axis.labelText, "Frequency (MHz)")

        before = self.bridge.blocks_written
        self.window._update_frequency_axes(1_296_300_000)
        QtTest.QTest.qWait(20)
        self.assertEqual(axes[0].tickStrings([0.0], 1.0, 0.1), ["1296.3000"])
        self.assertTrue(self.bridge.running)
        self.assertGreater(self.bridge.blocks_written, before)

    def test_radio_layout_axis_alignment_and_process_cpu_metric(self):
        radio_layout = self.window.receiver_group.parentWidget().layout()
        self.assertLess(radio_layout.indexOf(self.window.receiver_group), radio_layout.indexOf(self.window.frequency_card))
        self.assertLess(radio_layout.indexOf(self.window.frequency_card), radio_layout.indexOf(self.window.plot_card))

        spectrum_axis = self.window.split_spectrum_plot.getAxis("left")
        waterfall_axis = self.window.split_waterfall_plot.getAxis("left")
        self.assertEqual(spectrum_axis.width(), self.window.NORMAL_LEFT_AXIS_WIDTH)
        self.assertEqual(waterfall_axis.width(), self.window.NORMAL_LEFT_AXIS_WIDTH)
        frequencies = np.linspace(-0.75, 0.5, 256)
        self.window._set_plot_mode("split")
        self.window._draw_spectrum(frequencies, np.full(256, -90.0))
        QtWidgets.QApplication.processEvents()
        self.assertEqual(
            self.window.split_spectrum_plot.getViewBox().viewRange()[0],
            self.window.split_waterfall_plot.getViewBox().viewRange()[0],
        )

        self.window._last_cpu_wall = 10.0
        self.window._last_cpu_process = 1.0
        with (
            mock.patch("sdr_bridge.gui.time.monotonic", return_value=11.0),
            mock.patch("sdr_bridge.gui.time.process_time", return_value=2.5),
        ):
            self.assertAlmostEqual(self.window._update_process_cpu_metric(), 150.0)
        self.assertNotIn("%", self.window.cpu_label.text())
        self.assertEqual(self.window.cpu_label.text(), f"1.50 / {self.window._logical_cpu_count} cores")
        self.assertIn("logical cores used / available", self.window.cpu_metric.toolTip())

    def test_waterfall_is_the_default_and_hardware_capabilities_load_automatically(self):
        self.assertEqual(self.window._plot_mode, "waterfall")
        self.assertEqual(self.window.plot_stack.currentIndex(), 1)
        self.assertTrue(self.window.mode_waterfall.isChecked())
        self.assertTrue(self.window._capabilities)
        self.assertGreater(self.window.rate_combo.count(), 0)
        self.assertGreater(self.window.bandwidth_combo.count(), 0)

    def test_compact_contract_dimensions_and_text_state(self):
        self.window.toggle_compact()
        QtWidgets.QApplication.processEvents()
        self.assertGreaterEqual(self.window.minimumWidth(), 360)
        self.assertGreaterEqual(self.window.minimumHeight(), 100)
        self.assertTrue(self.window.compact_state.isHidden())
        self.assertEqual(self.window.compact_state.text(), "")
        self.assertIn("Hz", self.window.compact_frequency.text())
        self.assertTrue(self.window.compact_rx_button.property("success"))

    def test_compact_rx_button_restarts_and_shows_pending_state(self):
        self.window.toggle_compact()
        self.window.compact_rx_button.click()
        deadline = time.perf_counter() + 2.0
        while self.window._rx_action_busy and time.perf_counter() < deadline:
            QtTest.QTest.qWait(20)
        self.assertFalse(self.bridge.running)
        self.assertFalse(self.window.compact_rx_button.property("success"))

        original_start = self.bridge.start
        entered = threading.Event(); release = threading.Event()

        def slow_start():
            entered.set()
            release.wait(2.0)
            original_start()

        with mock.patch.object(self.bridge, "start", side_effect=slow_start):
            self.window.compact_rx_button.click()
            deadline = time.perf_counter() + 1.0
            while not entered.is_set() and time.perf_counter() < deadline:
                QtTest.QTest.qWait(10)
            self.window.refresh()
            self.assertTrue(entered.is_set())
            self.assertTrue(self.window.compact_rx_button.property("pending"))
            self.assertFalse(self.window.compact_rx_button.property("success"))
            self.assertTrue(self.window.start_button.property("pending"))
            self.assertIn("starting", self.window.status_bar.text().lower())
            release.set()
            deadline = time.perf_counter() + 2.0
            while self.window._rx_action_busy and time.perf_counter() < deadline:
                QtTest.QTest.qWait(20)

        self.assertFalse(self.window._rx_action_busy)
        self.assertTrue(self.bridge.running)
        self.assertTrue(self.window.compact_rx_button.property("success"))
        self.assertFalse(self.window.compact_rx_button.property("pending"))

    def test_simulation_indicator_and_adjustable_relative_db_scale(self):
        self.window.refresh()
        self.assertIn("Simulation", self.window.connection_label.text())
        self.window.y_min_spin.setValue(-130)
        self.window.y_max_spin.setValue(10)
        self.assertEqual(self.window.normal_plot.getViewBox().viewRange()[1], [-130.0, 10.0])

    def test_visible_display_scale_controls_adjust_spectrum_and_waterfall_without_interrupting_rx(self):
        self.assertTrue(self.window.y_min_slider.isVisibleTo(self.window))
        self.assertTrue(self.window.y_max_slider.isVisibleTo(self.window))
        before = self.bridge.blocks_written

        self.window.y_min_slider.setValue(-135)
        self.window.y_max_slider.setValue(-15)
        QtTest.QTest.qWait(40)

        self.assertEqual(self.window.normal_plot.getViewBox().viewRange()[1], [-135.0, -15.0])
        self.assertEqual(tuple(self.window.waterfall_image.getLevels()), (-135, -15))
        self.assertEqual(self.window.normal_curve.opts["fillLevel"], -135)
        self.assertEqual(self.window.split_spectrum_curve.opts["fillLevel"], -135)
        self.assertLess(self.window.y_max_slider.geometry().top(), self.window.y_min_slider.geometry().top())
        self.assertLessEqual(abs(self.window.y_max_slider.geometry().center().x() - self.window.y_min_slider.geometry().center().x()), 1)
        self.assertFalse(hasattr(self.window, "display_scale_title"))
        self.assertFalse(hasattr(self.window, "y_min_value"))
        self.assertFalse(hasattr(self.window, "y_max_value"))
        self.assertTrue(self.bridge.running)
        self.assertGreater(self.bridge.blocks_written, before)

    def test_file_source_is_named_explicitly(self):
        class NamedFileSource(SimulatedSource):
            @property
            def name(self):
                return "Fichier IQ int16 — SDR++_14.074MHz.wav"

        bridge = SDRBridge(NamedFileSource(block_samples=512), block_samples=512, slots=16)
        bridge.start()
        window = BridgeWindow(bridge)
        try:
            window.refresh()
            self.assertEqual(window.connection_label.text(), "Fichier IQ int16 — SDR++_14.074MHz.wav")
        finally:
            window.spectrum.close()
            window.hide()
            bridge.close()

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

    def test_bandwidth_auto_uses_closest_hardware_filter_and_keeps_manual_choices(self):
        native = object.__new__(NativeSDRplaySource)
        self.assertEqual(native.capabilities(native.DEVICE_ID).sample_rates_sps, (2_000_000, 6_000_000, 8_000_000, 10_000_000))
        self.window._capabilities = {
            "bandwidths_hz": (200_000, 300_000, 600_000, 1_536_000, 5_000_000, 6_000_000, 7_000_000, 8_000_000),
        }
        self.window._bandwidth_auto = True
        self.window._refresh_bandwidth_combo(4_000_000, 1_536_000)
        self.assertEqual(self.window.bandwidth_combo.currentIndex(), 0)
        self.assertEqual(self.window.bandwidth_combo.currentData(), 5_000_000)
        self.assertEqual(self.window.bandwidth_edit.text(), "5000000")
        self.assertEqual(
            [self.window.bandwidth_combo.itemData(i) for i in range(1, self.window.bandwidth_combo.count())],
            [200_000, 300_000, 600_000, 1_536_000, 5_000_000, 6_000_000, 7_000_000, 8_000_000],
        )
        self.window._refresh_bandwidth_combo(10_000_000, 1_536_000)
        self.assertEqual(self.window.bandwidth_combo.currentData(), 8_000_000)
        self.assertEqual(self.window.bandwidth_edit.text(), "8000000")
        RadioConfig(sample_rate_sps=4_000_000, bandwidth_hz=5_000_000).validate()

        self.window.rate_edit.setText("4000000")
        self.window.bandwidth_edit.setText("5000000")
        self.window._live_apply_timer.start()
        try:
            self.window.refresh()
            self.assertEqual(self.window.rate_edit.text(), "4000000")
            self.assertEqual(self.window.bandwidth_edit.text(), "5000000")
        finally:
            self.window._live_apply_timer.stop()

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

    def test_discovery_only_start_selects_first_receiver_and_loads_controls(self):
        selected = []
        self.bridge.device_id = None
        self.window._capabilities = {}
        self.window._capability_refresh_attempts = 0

        class RuntimeStub:
            recorder = None
            log_path = None

            def available_sources(runtime_self):
                return [
                    DeviceDescriptor(
                        SimulatedSource.DEVICE_ID, "simulated", "Simulation", "seed-1"
                    ).to_dict()
                ]

            def select_source_device(runtime_self, device_id):
                selected.append(device_id)
                self.bridge.select_device(device_id)

            def close(runtime_self):
                pass

        self.window.runtime = RuntimeStub()
        self.window._refresh_devices()

        self.assertEqual(selected, [SimulatedSource.DEVICE_ID])
        self.assertEqual(self.bridge.device_id, SimulatedSource.DEVICE_ID)
        self.assertTrue(self.window._capabilities)
        self.assertGreater(self.window.rate_combo.count(), 0)

    def test_rejected_source_selection_restores_effective_source(self):
        hardware_id = "soapy:sdrplay:test-rsp1a"

        class RuntimeStub:
            recorder = None
            log_path = None

            def available_sources(self):
                return [
                    DeviceDescriptor(SimulatedSource.DEVICE_ID, "simulated", "Simulation", "seed-1").to_dict(),
                    DeviceDescriptor(hardware_id, "soapy/sdrplay", "Test RSP1A", "test-rsp1a").to_dict(),
                ]

            def select_source_device(self, _device_id):
                raise RuntimeError("hardware reopen failed")

            def select_iq_file(self, _path, *, loop=False):
                raise AssertionError("not used")

            def close(self):
                pass

        self.window.runtime = RuntimeStub()
        self.window._refresh_devices()
        rejected_index = self.window.device_combo.findData(hardware_id)
        self.assertGreaterEqual(rejected_index, 0)

        self.window.device_combo.setCurrentIndex(rejected_index)
        QtWidgets.QApplication.processEvents()

        self.assertEqual(self.window.device_combo.currentData(), SimulatedSource.DEVICE_ID)
        self.assertTrue(self.window.error_banner.isVisible())
        self.assertIn("hardware reopen failed", self.window.error_banner.text())

    def test_source_dropdown_opens_native_iq_file_picker(self):
        class RuntimeStub:
            iq_file_path = None

            def __init__(self):
                self.selected = None

            def available_sources(self):
                return [item.to_dict() for item in self_window.bridge.source.enumerate()]

            def select_iq_file(self, path, *, loop=False):
                self.selected = (path, loop)

            def set_iq_file_loop(self, _enabled):
                pass

            def close(self):
                pass

        self_window = self.window
        runtime = RuntimeStub()
        self.window.runtime = runtime
        self.window._refresh_devices()
        picker_index = self.window.device_combo.findData(self.window.IQ_FILE_PICKER)
        self.assertGreaterEqual(picker_index, 0)
        self.assertIn("IQ file", self.window.device_combo.itemText(picker_index))
        selected_path = r"G:\IQ\HDSDR_144091kHz_RF.wav"
        with mock.patch.object(QtWidgets.QFileDialog, "getOpenFileName", return_value=(selected_path, "IQ recordings")):
            self.window.device_combo.setCurrentIndex(picker_index)
        self.assertEqual(runtime.selected, (selected_path, False))

    def test_capture_uses_native_save_dialog_and_default_captures_directory(self):
        class RuntimeStub:
            recorder = None

            def __init__(self):
                self.started = None

            def start_recording(self, path, profile_id, revision, capture_format):
                self.started = (path, profile_id, revision, capture_format)
                return Path(path)

            def close(self):
                pass

        runtime = RuntimeStub()
        self.window.runtime = runtime
        format_index = self.window.capture_format_combo.findData(CaptureFormat.SDRPP_WAV.value)
        self.assertGreaterEqual(format_index, 0)
        self.window.capture_format_combo.setCurrentIndex(format_index)
        selected_path = str(Path.cwd() / "Captures" / "chosen.wav")
        with (
            mock.patch.object(
                QtWidgets.QFileDialog,
                "getSaveFileName",
                return_value=(selected_path, "WAVE IQ recordings"),
            ) as picker,
            mock.patch.object(self.window, "refresh"),
        ):
            self.window._toggle_capture()

        self.assertIsNotNone(runtime.started)
        self.assertEqual(runtime.started[0], selected_path)
        self.assertEqual(runtime.started[3], CaptureFormat.SDRPP_WAV)
        default_path = Path(picker.call_args.args[2])
        self.assertEqual(default_path.parent, Path.cwd() / "Captures")
        self.assertIn("144300000Hz", default_path.name)
        self.assertTrue(default_path.name.endswith(".wav"))

    def test_antrack_style_digit_frequency_control_changes_one_digit(self):
        self.window.frequency_control.set_value_hz(144_300_000)
        values = []
        self.window.frequency_control.valueChanged.connect(values.append)
        self.window.frequency_control._apply_delta(1_000)
        self.assertEqual(self.window.frequency_control.value_hz(), 144_301_000)
        self.assertEqual(values[-1], 144_301_000)
        self.assertFalse(hasattr(self.window, "apply_button"))

    def test_frequency_leading_zeroes_are_dimmed_and_significant_digits_are_white(self):
        self.window.frequency_control.set_value_hz(144_300_000)
        self.assertIn("#7f8a94", self.window.frequency_control._digits[0].styleSheet())
        self.assertIn("#f4fbff", self.window.frequency_control._digits[3].styleSheet())

    def test_rsp1a_gains_are_mapped_to_two_inverted_reduction_controls(self):
        capabilities = {
            "gain_ranges": {"IFGR": (20, 59), "RFGR": (0, 9)},
            "gain_values": {"IFGR": 42, "RFGR": 4},
            "gain_steps": {"IFGR": 1, "RFGR": 1},
        }
        used = self.window._configure_primary_gains(capabilities)
        self.assertEqual(used, {"IFGR", "RFGR"})
        self.assertEqual(self.window._primary_gain_names, ["IFGR", "RFGR"])
        self.assertEqual((self.window.if_gain_slider.minimum(), self.window.if_gain_slider.maximum(), self.window.if_gain_slider.value()), (20, 59, 42))
        self.assertEqual((self.window.rf_gain_slider.minimum(), self.window.rf_gain_slider.maximum(), self.window.rf_gain_slider.value()), (0, 9, 4))
        self.assertTrue(self.window.if_gain_slider.invertedAppearance())
        self.assertTrue(self.window.rf_gain_slider.invertedAppearance())
        self.assertIn("reduction", self.window.if_gain_label.text())

    def test_file_source_disables_hardware_controls_but_keeps_values_visible(self):
        self.bridge.device_id = "file:test.wav"
        self.window.device_combo.clear()
        self.window.refresh()
        self.assertGreater(self.window.rate_combo.count(), 0)
        self.assertGreater(self.window.bandwidth_combo.count(), 0)
        self.assertFalse(self.window.frequency_control.isEnabled())
        self.assertFalse(self.window.rate_combo.isEnabled())
        self.assertFalse(self.window.bandwidth_combo.isEnabled())
        self.assertTrue(self.window.device_combo.isEnabled())

    def test_stopped_acquisition_button_is_not_green_and_about_credits_authors(self):
        self.bridge.stop(); self.window.refresh()
        self.assertFalse(self.window.start_button.property("success"))
        with mock.patch("sdr_bridge.gui.QtWidgets.QMessageBox.information") as information:
            self.window._open_about()
        message = information.call_args.args[2]
        self.assertIn("Stephane REY F1TJJ", message)
        self.assertIn("Philippe Borghini F5JWF", message)

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
        self.assertIn("SIMULATION", self.window.state_label.text())
        self.assertNotIn("SDRplay direct API", self.window.windowTitle())

    def test_waterfall_split_and_compact_follow_selected_mode(self):
        frequencies = np.linspace(-1.0, 1.0, 128)
        spectrum = np.linspace(-110.0, -30.0, 128)
        self.window._draw_spectrum(frequencies, spectrum)
        self.assertEqual(self.window._waterfall.shape, (180, 128))
        self.window._set_plot_mode("waterfall")
        self.assertEqual(self.window.plot_stack.currentIndex(), 1)
        self.assertEqual(self.window.compact_plot_stack.currentIndex(), 1)
        self.window._set_plot_mode("split")
        self.assertEqual(self.window.plot_stack.currentIndex(), 2)
        self.assertEqual(self.window.compact_plot_stack.currentIndex(), 2)

    def test_compact_consumer_count_includes_udp_destinations(self):
        class RuntimeStub:
            def close(self):
                pass

            def udp_destinations_snapshot(self):
                return [{
                    "destination": "127.0.0.1:7355", "transport": "sdbu_v2",
                    "configured_sample_rate_sps": 2_000_000, "datagram_bytes": 8192,
                    "queue_blocks": 32, "sent_packets": 1, "sent_bytes": 8192,
                    "dropped_blocks": 0, "socket_errors": 0, "last_center_frequency_hz": 144_300_000,
                }]

        self.window.runtime = RuntimeStub()
        self.window.refresh()
        expected = len(self.bridge.status()["clients"]) + 1
        self.assertEqual(self.window.compact_consumers.text(), f"{expected} consumers")

    def test_udp_destination_rate_datagram_and_queue_are_editable(self):
        class RuntimeStub:
            def __init__(self):
                self.updated = None

            def udp_destinations_snapshot(self):
                return [{
                    "destination": "127.0.0.1:7356", "transport": "sdrpp_raw_cs16",
                    "configured_sample_rate_sps": 192_000, "datagram_bytes": 8192,
                    "queue_blocks": 48, "sent_packets": 10, "sent_bytes": 81920,
                    "dropped_blocks": 0, "socket_errors": 0,
                    "last_center_frequency_hz": 144_300_000,
                }]

            def update_udp_destination(self, *args):
                self.updated = args

            def close(self):
                pass

        runtime = RuntimeStub()
        self.window.runtime = runtime
        self.window.refresh()
        self.window.destinations_table.selectRow(0)
        QtWidgets.QApplication.processEvents()
        self.assertEqual(self.window.destination_rate.value(), 192_000)
        self.assertEqual(self.window.destination_datagram.value(), 8192)
        self.assertEqual(self.window.destination_queue.value(), 48)
        self.window.destination_rate.setValue(1_000_000)
        self.window.destination_queue.setValue(64)
        self.window._update_udp_destination()
        self.assertEqual(runtime.updated, (
            "127.0.0.1:7356", "sdrpp_raw_cs16", 1_000_000, 8192, 64,
        ))

        self.window.destination_transport.setCurrentIndex(
            self.window.destination_transport.findData("qmap_linrad")
        )
        self.assertEqual(self.window.destination_rate.value(), 96_000)
        self.assertEqual(self.window.destination_datagram.value(), 1416)
        self.assertFalse(self.window.destination_rate.isEnabled())


if __name__ == "__main__":
    unittest.main()
