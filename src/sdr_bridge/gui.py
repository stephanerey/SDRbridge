from __future__ import annotations

from pathlib import Path
import threading
from typing import Any

import numpy as np
import pyqtgraph as pg
from PyQt5 import QtCore, QtGui, QtWidgets

from .bridge import SDRBridge, StaleConfigError
from . import __version__
from .dsp import payload_to_complex
from .frequency_control import FrequencyControlWidget
from .model import LifecycleState


class SpectrumService(QtCore.QObject):
    spectrumReady = QtCore.pyqtSignal(object, object)
    streamState = QtCore.pyqtSignal(bool)

    def __init__(self, bridge: SDRBridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.client_id, self.reader = bridge.register_client("GUI spectrum")
        self.fft_count = 0
        self.fft_size = 4096
        self.smoothing = 0.0
        self._smoothed_db = None


        self._last_block_ms = -1
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(67)
        self.timer.timeout.connect(self._poll)
        self.timer.start()

    def _poll(self) -> None:
        # A display only needs the newest complete block.  Draining the ring
        # here is incorrect at multi-MS/s rates: the producer can write faster
        # than the UI consumes, so the loop would never finish and the Qt
        # event loop would report a false "waiting for new blocks" state.
        latest = self.reader.read_latest(0.001)
        if latest is None:
            active = self._last_block_ms >= 0 and QtCore.QDateTime.currentMSecsSinceEpoch() - self._last_block_ms <= 2000
            self.streamState.emit(active)
            return
        self.bridge.record_read(self.client_id, latest.sequence, latest.sample_count, self.reader.dropped_blocks)
        samples = payload_to_complex(latest.payload, latest.sample_format)
        length = min(self.fft_size, len(samples))
        if length < 8:
            return
        # Keep a fixed reference.  Normalising every frame to its own peak
        # makes the trace look like an autoscaled Y axis even when the view
        # range is unchanged.  CS16 payloads are converted to approximately
        # full-scale complex samples by payload_to_complex, so the FFT is
        # expressed as stable dBFS (with the window coherent-gain correction).
        db = self.compute_dbfs(samples[:length])
        if self.smoothing > 0:
            if self._smoothed_db is None or self._smoothed_db.shape != db.shape:
                self._smoothed_db = db
            else:
                self._smoothed_db = self.smoothing * self._smoothed_db + (1.0 - self.smoothing) * db
            db = self._smoothed_db
        frequencies = np.fft.fftshift(np.fft.fftfreq(length, 1 / latest.sample_rate_sps)) / 1000.0
        self.fft_count += 1
        self._last_block_ms = QtCore.QDateTime.currentMSecsSinceEpoch()
        self.spectrumReady.emit(frequencies, db)
        self.streamState.emit(True)

    @staticmethod
    def compute_dbfs(samples: np.ndarray) -> np.ndarray:
        """Return a fixed-reference spectrum; no per-frame peak normalisation."""
        values = np.asarray(samples, dtype=np.complex64)
        window = np.hanning(len(values))
        coherent_gain = max(float(np.mean(window)), 1e-9)
        spectrum = np.fft.fftshift(np.fft.fft(values * window))
        amplitude = np.abs(spectrum) / max(1.0, len(values) * coherent_gain)
        return 20 * np.log10(np.maximum(amplitude, 1e-12))

    def close(self) -> None:
        self.timer.stop()
        self.bridge.unregister_client(self.client_id)

    def resync_after_reconfigure(self) -> None:
        self.reader.sync_latest()
        self._last_block_ms = -1
        self._smoothed_db = None


class GainTableDialog(QtWidgets.QDialog):
    """Small editable RF/IF calibration table used by Auto Table."""

    def __init__(self, rows: list[tuple[int, int, int, int]], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Gain calibration table")
        self.resize(600, 280)
        layout = QtWidgets.QVBoxLayout(self)
        self.table = QtWidgets.QTableWidget(len(rows), 4, self)
        self.table.setHorizontalHeaderLabels(["Minimum Hz", "Maximum Hz", "IF gain (dB)", "RF gain"])
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        for row, values in enumerate(rows):
            for column, value in enumerate(values):
                self.table.setItem(row, column, QtWidgets.QTableWidgetItem(str(value)))
        layout.addWidget(self.table)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def rows(self) -> list[tuple[int, int, int, int]]:
        result = []
        for row in range(self.table.rowCount()):
            values = []
            for column in range(4):
                item = self.table.item(row, column)
                values.append(int(item.text()) if item and item.text().strip() else 0)
            if values[1] > values[0]:
                result.append((values[0], values[1], values[2], values[3]))
        return sorted(result)


class BridgeWindow(QtWidgets.QMainWindow):
    configApplied = QtCore.pyqtSignal(object, object)

    def __init__(self, bridge: SDRBridge, runtime: Any | None = None):
        super().__init__()
        self.bridge = bridge
        self.runtime = runtime
        self._normal_geometry: QtCore.QByteArray | None = None
        self._config_apply_busy = False
        self._config_apply_pending: dict | None = None
        self._capabilities: dict[str, Any] = {}
        self._gain_table: list[tuple[int, int, int, int]] = [
            (1_000, 30_000_000, 40, 0),
            (30_000_000, 2_000_000_001, 40, 0),
        ]
        self._live_apply_timer = QtCore.QTimer(self)
        self._live_apply_timer.setSingleShot(True)
        self._live_apply_timer.setInterval(180)
        self._live_apply_timer.timeout.connect(self._apply_config)
        self.configApplied.connect(self._config_apply_finished)
        instance_name = getattr(runtime, "instance_name", "default") if runtime is not None else "default"
        self.setWindowTitle(f"SDRbridge {__version__} — RX — {instance_name}")
        self.setStyleSheet("""
            QWidget { color: #202124; background-color: #f4f5f7; font-size: 10pt; }
            QGroupBox { border: 1px solid #b8bec6; border-radius: 4px; margin-top: 8px; padding-top: 8px; }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 3px; }
            QLineEdit, QPlainTextEdit, QTableWidget, QComboBox { background: white; color: #202124; border: 1px solid #9aa1aa; }
            QPushButton { background: #e6e9ed; color: #202124; border: 1px solid #8d949d; border-radius: 3px; padding: 5px 10px; }
            QPushButton:hover { background: #d8e8f7; }
            QPushButton:disabled { color: #80868b; background: #eceff1; }
            QToolButton { background: transparent; color: #202124; border: 1px solid transparent; border-radius: 4px; padding: 4px 7px; }
            QToolButton:hover { background: #e3edf7; border-color: #9bb9d4; }
            QToolButton:pressed, QToolButton:checked { background: #d4e5f3; border-color: #6b9bc2; }
            QTabWidget::pane { border: 1px solid #aeb4bc; background: #f4f5f7; top: 0px; }
            QTabBar::tab { color: #59636e; background: #e3e6ea; padding: 6px 14px 5px 14px; min-width: 108px; border: 1px solid #aeb4bc; border-bottom-style: none; margin-right: -1px; }
            QTabBar::tab:first:!selected { border-top-left-radius: 4px; }
            QTabBar::tab:last { margin-right: 0; border-top-right-radius: 4px; }
            QTabBar::tab:!selected { margin-top: 2px; background: #e1e5e9; }
            QTabBar::tab:selected { color: #202124; background: white; font-weight: bold; border-bottom: 3px solid #4b88c7; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:!selected:hover { background: #d7e5f1; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QHeaderView::section { background: #e3e6ea; color: #202124; padding: 4px; border: 1px solid #c2c7ce; }
        """)
        self.resize(1100, 720)
        self.setMinimumSize(900, 600)
        self._stack = QtWidgets.QStackedWidget()
        self.setCentralWidget(self._stack)
        self._normal = self._build_normal()
        self._compact = self._build_compact()
        self._stack.addWidget(self._normal)
        self._stack.addWidget(self._compact)
        self.spectrum = SpectrumService(bridge, self)
        self.spectrum.spectrumReady.connect(self._draw_spectrum)
        self.spectrum.streamState.connect(self._stream_state)
        self._stats_timer = QtCore.QTimer(self)
        self._stats_timer.setInterval(1000)
        self._stats_timer.timeout.connect(self.refresh)
        self._stats_timer.start()
        self.refresh()

    def _build_topbar(self) -> QtWidgets.QWidget:
        bar = QtWidgets.QToolBar()
        bar.setMovable(False)
        bar.setFloatable(False)
        bar.setIconSize(QtCore.QSize(19, 19))
        bar.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        bar.setContentsMargins(6, 3, 6, 3)
        self.state_label = QtWidgets.QLabel("● Disconnected")
        self.state_label.setAccessibleName("RX state")
        self.frequency_effective = QtWidgets.QLabel("— Hz")
        self.start_button = QtWidgets.QToolButton()
        self.start_button.setAutoRaise(True)
        self.start_button.setAccessibleName("Start or stop SDR")
        self.start_button.setToolTip("Start SDR")
        self.start_button.clicked.connect(self._toggle_rx)
        self.compact_button = QtWidgets.QToolButton()
        self.compact_button.setAutoRaise(True)
        self.compact_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_TitleBarNormalButton))
        self.compact_button.setToolTip("Compact view")
        self.compact_button.clicked.connect(self.toggle_compact)
        self._play_icon = self.style().standardIcon(QtWidgets.QStyle.SP_MediaPlay)
        self._stop_icon = self.style().standardIcon(QtWidgets.QStyle.SP_MediaStop)
        self.start_button.setIcon(self._play_icon)
        bar.addWidget(self.state_label)
        bar.addSeparator()
        bar.addWidget(self.frequency_effective)
        spacer = QtWidgets.QWidget(); spacer.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        bar.addWidget(spacer)
        bar.addWidget(self.start_button)
        bar.addWidget(self.compact_button)
        return bar

    def _new_plot(self, compact=False) -> pg.PlotWidget:
        plot = pg.PlotWidget(background="#071521")
        plot.setMouseEnabled(x=False, y=False)
        plot.showGrid(x=True, y=True, alpha=.2)
        plot.setYRange(-90, 5)
        plot.setLabel("left", "Power (dBFS)")
        plot.setLabel("bottom", "Frequency offset", units="kHz")
        if compact:
            plot.hideAxis("left"); plot.hideAxis("bottom")
            plot.setFixedHeight(44)
        return plot

    def _build_normal(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget(); root = QtWidgets.QVBoxLayout(page); root.setContentsMargins(8, 8, 8, 8)
        root.addWidget(self._build_topbar())
        self.error_banner = QtWidgets.QLabel("")
        self.error_banner.setStyleSheet("background:#7a1f1f;color:white;padding:6px;")
        self.error_banner.setVisible(False); root.addWidget(self.error_banner)
        self.tabs = QtWidgets.QTabWidget(); root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._radio_tab(), "Radio")
        self.tabs.addTab(self._streams_tab(), "Outputs & Clients")
        self.tabs.addTab(self._rf_tab(), "RF Profiles")
        self.tabs.addTab(self._capture_tab(), "Captures")
        self.tabs.addTab(self._diagnostics_tab(), "Diagnostics")
        tab_bar = self.tabs.tabBar()
        tab_bar.setElideMode(QtCore.Qt.ElideNone)
        tab_bar.setExpanding(False)
        tab_bar.setUsesScrollButtons(False)
        self.status_bar = QtWidgets.QLabel("")
        root.addWidget(self.status_bar)
        return page

    def _radio_tab(self) -> QtWidgets.QWidget:
        tab = QtWidgets.QWidget(); layout = QtWidgets.QVBoxLayout(tab)
        cfg = self.bridge.config

        # Compatibility editors remain hidden so existing automation can still
        # set a value, but the visible control is the Antrack-style digit wheel.
        self.frequency_edit = QtWidgets.QLineEdit(str(cfg.center_frequency_hz), tab)
        self.frequency_edit.hide()
        self.rate_edit = QtWidgets.QLineEdit(str(cfg.sample_rate_sps), tab); self.rate_edit.hide()
        self.bandwidth_edit = QtWidgets.QLineEdit(str(cfg.bandwidth_hz), tab); self.bandwidth_edit.hide()
        self.gain_edit = QtWidgets.QLineEdit(str(cfg.gain_reduction_db), tab); self.gain_edit.hide()

        frequency_row = QtWidgets.QHBoxLayout()
        frequency_row.addWidget(QtWidgets.QLabel("SDR center frequency"))
        self.frequency_control = FrequencyControlWidget(tab)
        self.frequency_control.set_value_hz(cfg.center_frequency_hz)
        self.frequency_control.valueChanged.connect(self._frequency_changed)
        self.frequency_edit.editingFinished.connect(self._legacy_frequency_changed)
        frequency_row.addWidget(self.frequency_control, 1)
        layout.addLayout(frequency_row)

        source = QtWidgets.QGroupBox("Source")
        source_layout = QtWidgets.QVBoxLayout(source)

        source_top = QtWidgets.QGridLayout()
        self.device_combo = QtWidgets.QComboBox()
        self.device_combo.currentIndexChanged.connect(self._select_device)
        self.device_refresh_button = QtWidgets.QToolButton()
        self.device_refresh_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_BrowserReload))
        self.device_refresh_button.setToolTip("Refresh sources")
        self.device_refresh_button.setAccessibleName("Refresh sources")
        self.device_refresh_button.clicked.connect(self._refresh_devices)
        source_top.addWidget(QtWidgets.QLabel("Source"), 0, 0)
        source_top.addWidget(self.device_combo, 0, 1)
        source_top.addWidget(self.device_refresh_button, 0, 2)
        self.connection_label = QtWidgets.QLabel(""); self.connection_label.setWordWrap(True)
        source_top.addWidget(self.connection_label, 1, 0, 1, 3)
        source_layout.addLayout(source_top)

        controls = QtWidgets.QGridLayout()
        self.rate_combo = QtWidgets.QComboBox(); self.rate_combo.currentIndexChanged.connect(self._rate_changed)
        self.bandwidth_combo = QtWidgets.QComboBox(); self.bandwidth_combo.currentIndexChanged.connect(self._bandwidth_changed)
        self.antenna_combo = QtWidgets.QComboBox(); self.antenna_combo.currentIndexChanged.connect(lambda _index: self._schedule_live_apply())
        self.antenna_label = QtWidgets.QLabel("Antenna")
        controls.addWidget(QtWidgets.QLabel("Sampling"), 0, 0); controls.addWidget(self.rate_combo, 0, 1)
        controls.addWidget(QtWidgets.QLabel("Bandwidth"), 0, 2); controls.addWidget(self.bandwidth_combo, 0, 3)
        controls.addWidget(self.antenna_label, 0, 4); controls.addWidget(self.antenna_combo, 0, 5)
        self.if_gain_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.if_gain_slider.setRange(0, 100); self.if_gain_slider.setInvertedAppearance(True); self.if_gain_slider.setValue(cfg.gain_reduction_db)
        self.rf_gain_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.rf_gain_slider.setRange(0, 27); self.rf_gain_slider.setInvertedAppearance(True); self.rf_gain_slider.setValue(int(cfg.gains.get("lna_state", 0)))
        self.gain_slider = self.if_gain_slider  # historical attribute
        self.if_gain_slider.valueChanged.connect(lambda value: (self.gain_edit.setText(str(value)), self._schedule_live_apply()))
        self.rf_gain_slider.valueChanged.connect(lambda value: self._set_dynamic_value("lna_state", value))
        controls.addWidget(QtWidgets.QLabel("IF gain"), 1, 0); controls.addWidget(self.if_gain_slider, 1, 1)
        controls.addWidget(QtWidgets.QLabel("RF gain"), 1, 2); controls.addWidget(self.rf_gain_slider, 1, 3)
        self.agc_check = QtWidgets.QCheckBox("AGC"); self.agc_check.setChecked(cfg.agc_enabled); self.agc_check.stateChanged.connect(lambda _state: self._schedule_live_apply())
        self.auto_table_check = QtWidgets.QCheckBox("Auto Table"); self.auto_table_check.toggled.connect(self._auto_table_toggled)
        self.edit_table_button = QtWidgets.QPushButton("Edit"); self.edit_table_button.setMaximumWidth(56); self.edit_table_button.clicked.connect(self._edit_gain_table)
        controls.addWidget(self.auto_table_check, 1, 4); controls.addWidget(self.edit_table_button, 1, 5)
        source_layout.addLayout(controls)
        self.dynamic_container = QtWidgets.QWidget(source)
        self.extra_gains_form = QtWidgets.QHBoxLayout(self.dynamic_container)
        self.extra_gain_controls = {}
        options_row = QtWidgets.QHBoxLayout()
        options_row.addWidget(self.agc_check)
        options_row.addWidget(self.dynamic_container, 1)
        source_layout.addLayout(options_row)
        layout.addWidget(source)

        fft = QtWidgets.QGroupBox("Display processing")
        fft_form = QtWidgets.QHBoxLayout(fft)
        self.fft_size_combo = QtWidgets.QComboBox()
        self.fft_size_values = tuple(2 ** exponent for exponent in range(8, 18))
        for value in self.fft_size_values:
            self.fft_size_combo.addItem(f"{value:,}".replace(",", " "), value)
        self.fft_size_combo.setCurrentIndex(self.fft_size_values.index(4096))
        self.fft_size_combo.currentIndexChanged.connect(lambda index: setattr(self.spectrum, "fft_size", int(self.fft_size_combo.itemData(index))) if hasattr(self, "spectrum") else None)
        self.fft_size_spin = self.fft_size_combo  # compatibility attribute
        self.smoothing_spin = QtWidgets.QDoubleSpinBox(); self.smoothing_spin.setRange(0, .95); self.smoothing_spin.setSingleStep(.05); self.smoothing_spin.setValue(0); self.smoothing_spin.setToolTip("Exponential average: 0 disables smoothing")
        self.smoothing_spin.valueChanged.connect(lambda value: setattr(self.spectrum, "smoothing", float(value)) if hasattr(self, "spectrum") else None)
        fft_form.addWidget(QtWidgets.QLabel("FFT")); fft_form.addWidget(self.fft_size_combo); fft_form.addWidget(QtWidgets.QLabel("Smoothing")); fft_form.addWidget(self.smoothing_spin); fft_form.addStretch(1)
        layout.addWidget(fft)

        plot_row = QtWidgets.QHBoxLayout()
        self.normal_plot = self._new_plot(); self.normal_curve = self.normal_plot.plot(pen=pg.mkPen("#37D7FF", width=1.5)); plot_row.addWidget(self.normal_plot, 1)
        scale = QtWidgets.QVBoxLayout(); scale.addWidget(QtWidgets.QLabel("Max"), alignment=QtCore.Qt.AlignHCenter)
        self.y_max_slider = QtWidgets.QSlider(QtCore.Qt.Vertical); self.y_max_slider.setRange(-40, 20); self.y_max_slider.setValue(5); self.y_max_slider.setInvertedAppearance(True); self.y_max_slider.valueChanged.connect(self._apply_y_range)
        scale.addWidget(self.y_max_slider, 1, alignment=QtCore.Qt.AlignHCenter)
        scale.addWidget(QtWidgets.QLabel("Min"), alignment=QtCore.Qt.AlignHCenter)
        self.y_min_slider = QtWidgets.QSlider(QtCore.Qt.Vertical); self.y_min_slider.setRange(-160, -20); self.y_min_slider.setValue(-90); self.y_min_slider.valueChanged.connect(self._apply_y_range)
        scale.addWidget(self.y_min_slider, 1, alignment=QtCore.Qt.AlignHCenter)
        plot_row.addLayout(scale)
        # Compatibility handles for automation written against v0.3.  They
        # are not shown; the two vertical sliders above are the only front
        # panel controls.
        self.y_min_spin = QtWidgets.QDoubleSpinBox(source); self.y_min_spin.setRange(-160, -20); self.y_min_spin.setValue(-90); self.y_min_spin.hide()
        self.y_max_spin = QtWidgets.QDoubleSpinBox(source); self.y_max_spin.setRange(-40, 20); self.y_max_spin.setValue(5); self.y_max_spin.hide()
        self.y_min_spin.valueChanged.connect(lambda value: self.y_min_slider.setValue(int(value)))
        self.y_max_spin.valueChanged.connect(lambda value: self.y_max_slider.setValue(int(value)))
        layout.addLayout(plot_row, 1)
        return tab

    def _apply_y_range(self) -> None:
        low, high = self.y_min_slider.value(), self.y_max_slider.value()
        if high <= low:
            return
        self.normal_plot.setYRange(low, high, padding=0)
        if hasattr(self, "compact_plot"):
            self.compact_plot.setYRange(low, high, padding=0)

    def _sync_gain_slider(self, text: str) -> None:
        try:
            self.if_gain_slider.blockSignals(True)
            self.if_gain_slider.setValue(int(text))
        except ValueError:
            pass
        finally:
            self.if_gain_slider.blockSignals(False)

    def _frequency_changed(self, value: int) -> None:
        self.frequency_edit.setText(str(int(value)))
        if self.auto_table_check.isChecked():
            self._apply_gain_table(int(value))
        self._schedule_live_apply()

    def _legacy_frequency_changed(self) -> None:
        try:
            self.frequency_control.set_value_hz(int(self.frequency_edit.text()))
        except ValueError:
            return
        self._schedule_live_apply()

    def _rate_changed(self, index: int) -> None:
        if index < 0:
            return
        value = self.rate_combo.itemData(index)
        if value is not None:
            self.rate_edit.setText(str(int(value)))
            self._refresh_bandwidth_combo(int(value))
            self._schedule_live_apply()

    def _bandwidth_changed(self, index: int) -> None:
        if index < 0:
            return
        value = self.bandwidth_combo.itemData(index)
        if value is not None:
            self.bandwidth_edit.setText(str(int(value)))
            self._schedule_live_apply()

    def _set_dynamic_value(self, name: str, value: int) -> None:
        control = self.extra_gain_controls.get(name)
        if control is not None and control.value() != int(value):
            control.blockSignals(True); control.setValue(int(value)); control.blockSignals(False)
        self._schedule_live_apply()

    def _auto_table_toggled(self, enabled: bool) -> None:
        self.if_gain_slider.setEnabled(not enabled)
        self.rf_gain_slider.setEnabled(not enabled)
        if enabled:
            self._apply_gain_table(self.frequency_control.value_hz())
        self._schedule_live_apply()

    def _apply_gain_table(self, frequency_hz: int) -> None:
        for low, high, if_gain, rf_gain in self._gain_table:
            if low <= frequency_hz < high:
                self.if_gain_slider.setValue(max(self.if_gain_slider.minimum(), min(self.if_gain_slider.maximum(), if_gain)))
                self.rf_gain_slider.setValue(max(self.rf_gain_slider.minimum(), min(self.rf_gain_slider.maximum(), rf_gain)))
                return

    def _edit_gain_table(self) -> None:
        dialog = GainTableDialog(self._gain_table, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            rows = dialog.rows()
            if rows:
                self._gain_table = rows
                if self.auto_table_check.isChecked():
                    self._apply_gain_table(self.frequency_control.value_hz())
                    self._schedule_live_apply()

    def _refresh_devices(self) -> None:
        try:
            devices = self.bridge.enumerate_devices()
            current = self.bridge.device_id
            self.device_combo.blockSignals(True)
            self.device_combo.clear()
            for device in devices:
                label = device.get("model") or device.get("label") or device.get("device_id")
                serial = device.get("serial")
                suffix = f" — S/N {serial}" if serial and str(serial) not in str(label) else ""
                self.device_combo.addItem(f"{device.get('backend', '')}: {label}{suffix}", device.get("device_id"))
            if current:
                index = self.device_combo.findData(current)
                if index >= 0:
                    self.device_combo.setCurrentIndex(index)
                capabilities = self.bridge.capabilities(current)
                self._capabilities = capabilities
                gain_range = capabilities.get("gain_ranges", {}).get("gain_reduction_db", (0, 100))
                self.if_gain_slider.setRange(int(gain_range[0]), int(gain_range[1]))
                self.if_gain_slider.setValue(max(self.if_gain_slider.minimum(), min(self.if_gain_slider.maximum(), self.bridge.config.gain_reduction_db)))
                rf_range = capabilities.get("gain_ranges", {}).get("lna_state", (0, 27))
                self.rf_gain_slider.setRange(int(rf_range[0]), int(rf_range[1]))
                self.rf_gain_slider.setValue(int(self.bridge.config.gains.get("lna_state", rf_range[0])))
                self.agc_check.setEnabled(bool(capabilities.get("agc_available", False)))
                self._fill_capability_combo(self.rate_combo, capabilities.get("sample_rates_sps", ()), self.bridge.config.sample_rate_sps, "MHz")
                self._refresh_bandwidth_combo(self.bridge.config.sample_rate_sps, self.bridge.config.bandwidth_hz)
                self.antenna_combo.blockSignals(True)
                self.antenna_combo.clear()
                for antenna in capabilities.get("antennas", ()):
                    self.antenna_combo.addItem(str(antenna), str(antenna))
                antenna_index = self.antenna_combo.findData(self.bridge.config.antenna)
                if antenna_index >= 0:
                    self.antenna_combo.setCurrentIndex(antenna_index)
                self.antenna_combo.blockSignals(False)
                while self.extra_gains_form.count():
                    item = self.extra_gains_form.takeAt(0)
                    if item.widget() is not None:
                        item.widget().deleteLater()
                self.extra_gain_controls.clear()
                labels = {
                    "bias_t_enabled": "Bias-T", "rf_notch_enabled": "FM Notch",
                    "rf_dab_notch_enabled": "DAB Notch", "hdr_enabled": "HDR",
                    "hdr_bw": "HDR bandwidth", "if_type": "IF filter",
                }
                for name, bounds in capabilities.get("gain_ranges", {}).items():
                    if name in {"gain_reduction_db", "lna_state"}:
                        continue
                    low, high = map(float, bounds)
                    value = float(self.bridge.config.gains.get(name, low))
                    if name.endswith("_enabled"):
                        control = QtWidgets.QCheckBox(labels.get(name, name.replace("_", " ").title()))
                        control.setChecked(bool(value)); control.stateChanged.connect(lambda _state: self._schedule_live_apply())
                    elif name in {"hdr_bw", "if_type"}:
                        control = QtWidgets.QComboBox()
                        options = (("0.2 MHz", 0), ("0.5 MHz", 1), ("1.2 MHz", 2), ("1.7 MHz", 3)) if name == "hdr_bw" else (("0 kHz", 0), ("450 kHz", 1), ("1,620 kHz", 2), ("2,048 kHz", 3))
                        for label, option in options:
                            control.addItem(label, option)
                        control.setCurrentIndex(max(0, min(3, round(value)))); control.currentIndexChanged.connect(lambda _index: self._schedule_live_apply())
                    else:
                        control = QtWidgets.QSlider(QtCore.Qt.Horizontal); control.setRange(round(low), round(high)); control.setValue(round(value)); control.valueChanged.connect(lambda _value: self._schedule_live_apply())
                    if name.endswith("_enabled"):
                        self.extra_gains_form.addWidget(control)
                    else:
                        holder = QtWidgets.QWidget(self.dynamic_container)
                        row = QtWidgets.QHBoxLayout(holder); row.setContentsMargins(3, 0, 3, 0)
                        row.addWidget(QtWidgets.QLabel(labels.get(name, name.replace("_", " ").title())))
                        row.addWidget(control)
                        self.extra_gains_form.addWidget(holder)
                    self.extra_gain_controls[name] = control
                self.dynamic_container.setVisible(bool(self.extra_gain_controls))
            self.device_combo.blockSignals(False)
        except Exception as exc:
            self.device_combo.clear(); self.device_combo.addItem(f"Discovery unavailable: {exc}")

    @staticmethod
    def _fill_capability_combo(combo, values, current, unit: str) -> None:
        combo.blockSignals(True); combo.clear()
        values = [int(value) for value in values]
        for value in values:
            shown = f"{value / 1e6:.3f} MHz" if unit == "MHz" else f"{value / 1e6:.3f} MHz"
            combo.addItem(shown, value)
        if values:
            index = min(range(len(values)), key=lambda i: abs(values[i] - int(current)))
            combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def _refresh_bandwidth_combo(self, sample_rate_sps: int, current_bandwidth_hz: int | None = None) -> None:
        """Show only tuner filters valid for the selected ADC sample rate."""
        all_bandwidths = tuple(int(value) for value in self._capabilities.get("bandwidths_hz", ()))
        valid = tuple(value for value in all_bandwidths if value <= int(sample_rate_sps))
        if not valid:
            valid = all_bandwidths[:1]
        current = int(current_bandwidth_hz if current_bandwidth_hz is not None else self.bandwidth_edit.text())
        selected = min(valid, key=lambda value: abs(value - current)) if valid else None
        existing = tuple(int(self.bandwidth_combo.itemData(i)) for i in range(self.bandwidth_combo.count()))
        if existing == valid and self.bandwidth_combo.currentData() == selected:
            return
        self._fill_capability_combo(self.bandwidth_combo, valid, current, "kHz")
        if valid and current not in valid:
            # Keep the draft valid when lowering Sampling below the current
            # filter width; prefer the widest filter still supported.
            fallback = max(valid)
            self.bandwidth_edit.setText(str(fallback))

    def _select_device(self, index: int) -> None:
        device_id = self.device_combo.itemData(index)
        if not device_id or device_id == self.bridge.device_id:
            return
        try:
            self.bridge.select_device(str(device_id))
            self._show_error("")
            self._refresh_devices()
        except Exception as exc:
            self._show_error(f"Device rejected — {exc}")
        self.refresh()

    def _streams_tab(self) -> QtWidgets.QWidget:
        tab = QtWidgets.QWidget(); layout = QtWidgets.QVBoxLayout(tab)
        self.profiles_table = QtWidgets.QTableWidget(0, 5)
        self.profiles_table.setHorizontalHeaderLabels(["Profile", "Rate", "Format", "Protocol", "Revision"])
        profiles = self.bridge.profiles.items(); self.profiles_table.setRowCount(len(profiles))
        for row, profile in enumerate(profiles):
            for column, value in enumerate((profile.name or profile.profile_id, profile.output_rate_sps, profile.sample_format.value, profile.protocol, profile.profile_revision)):
                self.profiles_table.setItem(row, column, QtWidgets.QTableWidgetItem(str(value)))
        self.profiles_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        layout.addWidget(QtWidgets.QLabel("Published immutable profiles")); layout.addWidget(self.profiles_table)
        self.clients_table = QtWidgets.QTableWidget(0, 4)
        self.clients_table.setHorizontalHeaderLabels(["Client", "Blocks read", "Ring drops", "Last sequence"])
        self.clients_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        layout.addWidget(QtWidgets.QLabel("Confirmed local clients (separate UDP destinations)")); layout.addWidget(self.clients_table)
        self.destinations_table = QtWidgets.QTableWidget(0, 8)
        self.destinations_table.setHorizontalHeaderLabels(["Destination", "Transport", "Packets", "Bytes", "Queue drops", "Errors", "Center frequency", "Rate"])
        self.destinations_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.destinations_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        layout.addWidget(QtWidgets.QLabel("UDP clients / destinations")); layout.addWidget(self.destinations_table)
        destination_controls = QtWidgets.QHBoxLayout()
        self.destination_edit = QtWidgets.QLineEdit("127.0.0.1:7356")
        self.destination_edit.setPlaceholderText("HOST:PORT")
        self.destination_transport = QtWidgets.QComboBox()
        self.destination_transport.addItem("SDR++ raw CS16", "sdrpp_raw_cs16")
        self.destination_transport.addItem("SDBU v2", "sdbu_v2")
        self.add_destination_button = QtWidgets.QPushButton("Add client")
        self.add_destination_button.clicked.connect(self._add_udp_destination)
        self.remove_destination_button = QtWidgets.QPushButton("Remove")
        self.remove_destination_button.clicked.connect(self._remove_udp_destination)
        destination_controls.addWidget(QtWidgets.QLabel("Endpoint")); destination_controls.addWidget(self.destination_edit, 1)
        destination_controls.addWidget(self.destination_transport); destination_controls.addWidget(self.add_destination_button); destination_controls.addWidget(self.remove_destination_button)
        layout.addLayout(destination_controls)
        layout.addWidget(QtWidgets.QLabel("SDR++ raw clients are passive: they receive the selected UDP destination but do not create a confirmed control session."))
        if self.runtime is None or not hasattr(self.runtime, "add_udp_destination"):
            self.add_destination_button.setEnabled(False); self.remove_destination_button.setEnabled(False)
        network_enabled = bool(getattr(self.runtime, "native_control", None))
        layout.addWidget(QtWidgets.QLabel("Native loopback control enabled" if network_enabled else "Native network disabled by configuration"))
        return tab

    def _add_udp_destination(self) -> None:
        if self.runtime is None or not hasattr(self.runtime, "add_udp_destination"):
            self._show_error("UDP destination management is unavailable")
            return
        try:
            self.runtime.add_udp_destination(self.destination_edit.text().strip(), self.destination_transport.currentData())
            self._show_error("")
            self.refresh()
        except Exception as exc:
            self._show_error(f"Client rejected — {exc}")

    def _remove_udp_destination(self) -> None:
        if self.runtime is None or not hasattr(self.runtime, "remove_udp_destination"):
            self._show_error("UDP destination management is unavailable")
            return
        row = self.destinations_table.currentRow()
        if row < 0 or self.destinations_table.item(row, 0) is None:
            self._show_error("Select a UDP client first")
            return
        try:
            self.runtime.remove_udp_destination(self.destinations_table.item(row, 0).text())
            self._show_error("")
            self.refresh()
        except Exception as exc:
            self._show_error(f"Client removal failed — {exc}")

    def _rf_tab(self) -> QtWidgets.QWidget:
        tab = QtWidgets.QWidget(); layout = QtWidgets.QVBoxLayout(tab)
        layout.addWidget(QtWidgets.QLabel("No RF rules registered. Ranges are [min, max[ and equal-priority overlaps are rejected."))
        table = QtWidgets.QTableWidget(0, 6); table.setHorizontalHeaderLabels(["ID", "Min Hz", "Max Hz", "Priority", "Antenna", "State"])
        table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch); layout.addWidget(table)
        return tab

    def _capture_tab(self) -> QtWidgets.QWidget:
        tab = QtWidgets.QWidget(); layout = QtWidgets.QFormLayout(tab)
        self.capture_path = QtWidgets.QLineEdit(str(Path.cwd() / "capture"))
        self.capture_profile = QtWidgets.QComboBox()
        for profile in self.bridge.profiles.items():
            if profile.protocol in {"ring_v2", "sdbu_v2"}:
                self.capture_profile.addItem(profile.name or profile.profile_id, (profile.profile_id, profile.profile_revision))
        self.capture_button = QtWidgets.QPushButton("Start capture")
        self.capture_button.clicked.connect(self._toggle_capture)
        self.capture_status = QtWidgets.QLabel("Recorder stopped")
        layout.addRow("SigMF file base", self.capture_path)
        layout.addRow("Profile", self.capture_profile)
        layout.addRow(self.capture_button); layout.addRow(self.capture_status)
        layout.addRow(QtWidgets.QLabel("A discontinuity closes the capture; existing files are never overwritten."))
        return tab

    def _diagnostics_tab(self) -> QtWidgets.QWidget:
        tab = QtWidgets.QWidget(); layout = QtWidgets.QVBoxLayout(tab)
        self.diagnostics = QtWidgets.QPlainTextEdit(); self.diagnostics.setReadOnly(True)
        layout.addWidget(self.diagnostics)
        return tab

    def _build_compact(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget(); layout = QtWidgets.QVBoxLayout(page); layout.setContentsMargins(5, 3, 5, 3); layout.setSpacing(2)
        top = QtWidgets.QHBoxLayout()
        self.compact_state = QtWidgets.QLabel("IDLE")
        self.compact_frequency = QtWidgets.QLabel("— Hz")
        normal = QtWidgets.QPushButton("Normal"); normal.clicked.connect(self.toggle_compact)
        self.always_on_top = QtWidgets.QCheckBox("Always on top"); self.always_on_top.toggled.connect(self._always_on_top)
        top.addWidget(self.compact_state); top.addWidget(self.compact_frequency); top.addStretch(1); top.addWidget(self.always_on_top); top.addWidget(normal)
        layout.addLayout(top)
        self.compact_plot = self._new_plot(True); self.compact_curve = self.compact_plot.plot(pen=pg.mkPen("#37D7FF", width=1.2)); layout.addWidget(self.compact_plot)
        bottom = QtWidgets.QHBoxLayout(); self.compact_stats = QtWidgets.QLabel(""); stop = QtWidgets.QToolButton(); stop.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MediaStop)); stop.setToolTip("Stop SDR"); stop.clicked.connect(self._stop_rx)
        bottom.addWidget(self.compact_stats); bottom.addStretch(1); bottom.addWidget(stop); layout.addLayout(bottom)
        return page

    def _draw_spectrum(self, frequencies, db) -> None:
        self.normal_curve.setData(frequencies, db)
        self.compact_curve.setData(frequencies, db)

    def _stream_state(self, active: bool) -> None:
        if not active and self.bridge.running:
            self.status_bar.setText("RX active — waiting for new blocks (spectrum display delayed)")
            self.normal_curve.setPen(pg.mkPen("#6b7780")); self.compact_curve.setPen(pg.mkPen("#6b7780"))
        else:
            self.normal_curve.setPen(pg.mkPen("#37D7FF")); self.compact_curve.setPen(pg.mkPen("#37D7FF"))

    def _show_error(self, text: str) -> None:
        self.error_banner.setText(text); self.error_banner.setVisible(bool(text))

    def _toggle_rx(self) -> None:
        try:
            if self.bridge.running:
                self.bridge.stop()
            else:
                self.bridge.start()
            self._show_error("")
        except Exception as exc:
            self._show_error(str(exc))
        self.refresh()

    def _stop_rx(self) -> None:
        if self.bridge.running:
            try:
                self.bridge.stop()
            except Exception as exc:
                self._show_error(str(exc))
        self.refresh()

    def _apply_config(self) -> None:
        try:
            requested = self._draft_config()
        except Exception as exc:
            self._show_error(f"Configuration rejected — {exc}")
            self.refresh()
            return
        if self._config_apply_busy:
            # Un déplacement de slider peut produire plusieurs événements.
            # On ne garde que le dernier brouillon, jamais une file de mises
            # à jour obsolètes.
            self._config_apply_pending = requested
            return
        self._config_apply_busy = True
        self.status_bar.setText("Applying hot SDR update…")

        def worker(payload: dict) -> None:
            result = None
            error = None
            try:
                result = self.bridge.apply_config(self.bridge.config.revision, payload)
            except BaseException as exc:  # transmis au thread Qt principal
                error = exc
            self.configApplied.emit(result, error)

        threading.Thread(target=worker, args=(requested,), name="sdr-config-update", daemon=True).start()

    def _draft_config(self) -> dict:
        # The hidden line edits provide a compatibility path for scripts that
        # used the former text controls; visible user interaction uses the
        # digit widget and capability comboboxes.
        return {
            "center_frequency_hz": int(self.frequency_edit.text()),
            "sample_rate_sps": int(self.rate_edit.text()),
            "bandwidth_hz": int(self.bandwidth_edit.text()),
            "gain_reduction_db": int(self.gain_edit.text()),
            "agc_enabled": self.agc_check.isChecked(),
            "antenna": self.antenna_combo.currentData() or None,
            "gains": {
                **{name: self._control_value(control) for name, control in self.extra_gain_controls.items()},
                "lna_state": int(self.rf_gain_slider.value()),
            },
        }

    def _schedule_live_apply(self) -> None:
        if not getattr(self, "_live_apply_timer", None):
            return
        self._live_apply_timer.start()

    @QtCore.pyqtSlot(object, object)
    def _config_apply_finished(self, result, error) -> None:
        self._config_apply_busy = False
        if error is None:
            self.spectrum.resync_after_reconfigure()
            self._show_error("")
        elif isinstance(error, StaleConfigError):
            self._show_error("STALE_CONFIG — effective values were reloaded")
        else:
            self._show_error(f"Configuration rejected — {error}")
        pending = self._config_apply_pending
        self._config_apply_pending = None
        self.refresh()
        if pending is not None:
            # Rejoue explicitement le dernier brouillon sans dépendre d'un
            # signal widget qui aurait déjà été consommé.
            self._config_apply_pending = pending
            QtCore.QTimer.singleShot(0, self._apply_pending_config)

    def _apply_pending_config(self) -> None:
        pending = self._config_apply_pending
        self._config_apply_pending = None
        if pending is None:
            return
        if self._config_apply_busy:
            self._config_apply_pending = pending
            return
        self._config_apply_busy = True
        def worker(payload: dict) -> None:
            result = None; error = None
            try:
                result = self.bridge.apply_config(self.bridge.config.revision, payload)
            except BaseException as exc:
                error = exc
            self.configApplied.emit(result, error)
        threading.Thread(target=worker, args=(pending,), name="sdr-config-update", daemon=True).start()

    @staticmethod
    def _control_value(control):
        if isinstance(control, QtWidgets.QCheckBox):
            return 1 if control.isChecked() else 0
        if isinstance(control, QtWidgets.QComboBox):
            return control.currentData()
        return control.value()

    def _toggle_capture(self) -> None:
        if self.runtime is None:
            self._show_error("Recorder unavailable in this context")
            return
        try:
            if self.runtime.recorder is None:
                profile_id, revision = self.capture_profile.currentData()
                self.runtime.start_recording(self.capture_path.text(), profile_id, revision)
            else:
                self.runtime.stop_recording("operator stop")
            self._show_error("")
        except Exception as exc:
            self._show_error(str(exc))
        self.refresh()

    def toggle_compact(self) -> None:
        if self._stack.currentIndex() == 0:
            self._normal_geometry = self.saveGeometry()
            self._stack.setCurrentIndex(1); self.setMinimumSize(360, 100); self.resize(480, 120)
        else:
            self._stack.setCurrentIndex(0); self.setMinimumSize(900, 600)
            if self._normal_geometry:
                self.restoreGeometry(self._normal_geometry)
            else:
                self.resize(1100, 720)

    def _always_on_top(self, enabled: bool) -> None:
        self.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, enabled)
        self.show()

    def refresh(self) -> None:
        status = self.bridge.status(); cfg = status["config"]; state = status["state"]
        connected = state == "RUNNING"
        self.state_label.setText("● Connected" if connected else ("● Error" if state == "ERROR" else "○ Disconnected"))
        self.compact_state.setText(f"RX {state}")
        color = "#157A36" if connected else ("#9b1c1c" if state == "ERROR" else "#595959")
        self.state_label.setStyleSheet(f"font-weight:bold;color:{color}"); self.compact_state.setStyleSheet(f"font-weight:bold;color:{color}")
        frequency = f"{cfg['center_frequency_hz']:,} Hz".replace(",", " ")
        self.frequency_effective.setText(frequency); self.compact_frequency.setText(frequency)
        self.start_button.setIcon(self._stop_icon if self.bridge.running else self._play_icon)
        self.start_button.setToolTip("Stop SDR" if self.bridge.running else "Start SDR")
        if self.device_combo.count() == 0:
            self._refresh_devices()
        source_name = status["source"]
        if source_name.lower().startswith("source simul") or "simulat" in source_name.lower():
            self.connection_label.setText("Simulation")
            self.connection_label.setStyleSheet("color:#8a5200")
        elif state == "RUNNING":
            self.connection_label.setText("Connected")
            self.connection_label.setStyleSheet("color:#157A36")
        else:
            self.connection_label.setText("Not connected")
            self.connection_label.setStyleSheet("color:#595959")
        disabled = state in {"OPENING", "RECONFIGURING", "STOPPING", "STARTING"}
        if not self._config_apply_busy:
            self.frequency_control.set_value_hz(cfg["center_frequency_hz"])
            self.frequency_edit.setText(str(cfg["center_frequency_hz"]))
            self.rate_edit.setText(str(cfg["sample_rate_sps"]))
            self.bandwidth_edit.setText(str(cfg["bandwidth_hz"]))
            self.gain_edit.setText(str(cfg["gain_reduction_db"]))
            if self._capabilities:
                self._refresh_bandwidth_combo(cfg["sample_rate_sps"], cfg["bandwidth_hz"])
        self._apply_y_range()
        clients = status["clients"]; self.clients_table.setRowCount(len(clients))
        for row, client in enumerate(clients):
            for column, value in enumerate((client["name"], client["blocks_read"], client["dropped_blocks"], client["last_sequence"])):
                self.clients_table.setItem(row, column, QtWidgets.QTableWidgetItem(str(value)))
        destinations = []
        if self.runtime is not None and hasattr(self.runtime, "udp_destinations_snapshot"):
            destinations = self.runtime.udp_destinations_snapshot()
        else:
            operator_udp = getattr(self.runtime, "operator_udp", None)
            destinations = [] if operator_udp is None else [operator_udp.destination.snapshot()]
        self.destinations_table.setRowCount(len(destinations))
        for row, item in enumerate(destinations):
            values = (item["destination"], item["transport"], item["sent_packets"], item["sent_bytes"], item["dropped_blocks"], item["socket_errors"], item.get("last_center_frequency_hz") or "—", item.get("last_sample_rate_sps") or "—")
            for column, value in enumerate(values):
                self.destinations_table.setItem(row, column, QtWidgets.QTableWidgetItem(str(value)))
        self.status_bar.setText(f"{status['sample_rate_measured']/1e6:.3f} MS/s | source queue drops {status['source_queue_drops']} | errors {status['source_errors']}")
        self.compact_stats.setText(f"{len(clients)} clients | drops {status['source_queue_drops']}")
        recorder = getattr(self.runtime, "recorder", None)
        if recorder:
            self.capture_status.setText(f"Capture active — {recorder.bytes_written} bytes")
            self.capture_button.setText("Stop capture")
        else:
            self.capture_status.setText("Recorder stopped")
            self.capture_button.setText("Start capture")
        diagnostics = {key: status[key] for key in ("state", "source", "source_id", "epoch", "blocks_received", "blocks_written", "source_queue_drops", "source_queue_capacity", "source_queue_high_water", "source_errors", "dispatch_processing_average_ms", "dispatch_processing_max_ms", "dispatch_slow_blocks", "last_error", "pipelines")}
        diagnostics["capabilities"] = self._capabilities
        diagnostics["log_file"] = str(self.runtime.log_path) if self.runtime is not None and getattr(self.runtime, "log_path", None) else None
        import json
        self.diagnostics.setPlainText(json.dumps(diagnostics, ensure_ascii=False, indent=2))

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        recorder_active = bool(getattr(self.runtime, "recorder", None))
        if self.bridge.running or recorder_active:
            answer = QtWidgets.QMessageBox.question(self, "Quit SDRbridge", "Stop reception and quit?", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Cancel)
            if answer != QtWidgets.QMessageBox.Yes:
                event.ignore(); return
        self.spectrum.close()
        if self.runtime:
            self.runtime.close()
        else:
            self.bridge.close()
        event.accept()


def run_gui(bridge: SDRBridge, runtime: Any | None = None) -> int:
    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    application.setApplicationName("SDRbridge")
    application.setStyle("Fusion")
    window = BridgeWindow(bridge, runtime)
    window.show()
    return application.exec_()


BridgeGUI = BridgeWindow
