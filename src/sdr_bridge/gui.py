from __future__ import annotations

from pathlib import Path
import threading
from typing import Any

import numpy as np
import pyqtgraph as pg
from PyQt5 import QtCore, QtGui, QtWidgets

from .bridge import SDRBridge, StaleConfigError
from .dsp import payload_to_complex
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
        latest = None
        while True:
            block = self.reader.read(0.0001)
            if block is None:
                break
            latest = block
        if latest is None:
            active = self._last_block_ms >= 0 and QtCore.QDateTime.currentMSecsSinceEpoch() - self._last_block_ms <= 2000
            self.streamState.emit(active)
            return
        self.bridge.record_read(self.client_id, latest.sequence, latest.sample_count, self.reader.dropped_blocks)
        samples = payload_to_complex(latest.payload, latest.sample_format)
        length = min(self.fft_size, len(samples))
        if length < 8:
            return
        spectrum = np.fft.fftshift(np.fft.fft(samples[:length] * np.hanning(length)))
        db = 20 * np.log10(np.maximum(np.abs(spectrum), 1e-12))
        db -= np.max(db)
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

    def close(self) -> None:
        self.timer.stop()
        self.bridge.unregister_client(self.client_id)

    def resync_after_reconfigure(self) -> None:
        self.reader.sync_latest()
        self._last_block_ms = -1
        self._smoothed_db = None


class BridgeWindow(QtWidgets.QMainWindow):
    configApplied = QtCore.pyqtSignal(object, object)

    def __init__(self, bridge: SDRBridge, runtime: Any | None = None):
        super().__init__()
        self.bridge = bridge
        self.runtime = runtime
        self._normal_geometry: QtCore.QByteArray | None = None
        self._config_apply_busy = False
        self._config_apply_pending: dict | None = None
        self._live_apply_timer = QtCore.QTimer(self)
        self._live_apply_timer.setSingleShot(True)
        self._live_apply_timer.setInterval(180)
        self._live_apply_timer.timeout.connect(self._apply_config)
        self.configApplied.connect(self._config_apply_finished)
        self.setWindowTitle("SDRbridge 0.3 — RX")
        self.setStyleSheet("""
            QWidget { color: #202124; background-color: #f4f5f7; font-size: 10pt; }
            QGroupBox { border: 1px solid #b8bec6; border-radius: 4px; margin-top: 8px; padding-top: 8px; }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 3px; }
            QLineEdit, QPlainTextEdit, QTableWidget, QComboBox { background: white; color: #202124; border: 1px solid #9aa1aa; }
            QPushButton { background: #e6e9ed; color: #202124; border: 1px solid #8d949d; border-radius: 3px; padding: 5px 10px; }
            QPushButton:hover { background: #d8e8f7; }
            QPushButton:disabled { color: #80868b; background: #eceff1; }
            QTabWidget::pane { border: 1px solid #aeb4bc; background: #f4f5f7; }
            QTabBar::tab { background: #e3e6ea; color: #202124; padding: 7px 14px; border: 1px solid #aeb4bc; }
            QTabBar::tab:selected { background: white; font-weight: bold; }
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
        bar = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(bar); layout.setContentsMargins(8, 6, 8, 6)
        self.source_label = QtWidgets.QLabel(self.bridge.source.name)
        self.state_label = QtWidgets.QLabel("IDLE")
        self.state_label.setAccessibleName("État de réception")
        self.frequency_effective = QtWidgets.QLabel("— Hz")
        self.start_button = QtWidgets.QPushButton("Démarrer")
        self.start_button.clicked.connect(self._toggle_rx)
        self.compact_button = QtWidgets.QPushButton("Compact")
        self.compact_button.clicked.connect(self.toggle_compact)
        for widget in (self.source_label, self.state_label, self.frequency_effective):
            layout.addWidget(widget)
        layout.addStretch(1); layout.addWidget(self.start_button); layout.addWidget(self.compact_button)
        return bar

    def _new_plot(self, compact=False) -> pg.PlotWidget:
        plot = pg.PlotWidget(background="#071521")
        plot.setMouseEnabled(x=False, y=False)
        plot.showGrid(x=True, y=True, alpha=.2)
        plot.setYRange(-90, 5)
        plot.setLabel("left", "dB relatif (pic = 0)")
        plot.setLabel("bottom", "Écart fréquence", units="kHz")
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
        self.tabs.addTab(self._streams_tab(), "Sorties et clients")
        self.tabs.addTab(self._rf_tab(), "Profils RF")
        self.tabs.addTab(self._capture_tab(), "Captures")
        self.tabs.addTab(self._diagnostics_tab(), "Diagnostics")
        self.status_bar = QtWidgets.QLabel("")
        root.addWidget(self.status_bar)
        return page

    def _radio_tab(self) -> QtWidgets.QWidget:
        tab = QtWidgets.QWidget(); layout = QtWidgets.QVBoxLayout(tab)
        device = QtWidgets.QGroupBox("Périphérique et réglages RX effectifs")
        form = QtWidgets.QGridLayout(device)
        cfg = self.bridge.config
        self.frequency_edit = QtWidgets.QLineEdit(str(cfg.center_frequency_hz))
        self.rate_edit = QtWidgets.QLineEdit(str(cfg.sample_rate_sps))
        self.bandwidth_edit = QtWidgets.QLineEdit(str(cfg.bandwidth_hz))
        self.gain_edit = QtWidgets.QLineEdit(str(cfg.gain_reduction_db))
        self.gain_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.gain_slider.setRange(0, 100); self.gain_slider.setValue(cfg.gain_reduction_db)
        self.gain_slider.valueChanged.connect(lambda value: self.gain_edit.setText(str(value)))
        self.gain_slider.valueChanged.connect(lambda _value: self._schedule_live_apply())
        self.gain_edit.textChanged.connect(self._sync_gain_slider)
        self.agc_check = QtWidgets.QCheckBox("AGC"); self.agc_check.setChecked(cfg.agc_enabled)
        for field in (self.frequency_edit, self.rate_edit, self.bandwidth_edit, self.gain_edit):
            field.editingFinished.connect(self._schedule_live_apply)
        self.agc_check.stateChanged.connect(lambda _state: self._schedule_live_apply())
        fields = (("Fréquence demandée (Hz)", self.frequency_edit), ("Taux demandé (S/s)", self.rate_edit), ("Bande demandée (Hz)", self.bandwidth_edit), ("Gain IF / réduction gRdB (dB)", self.gain_edit))
        for row, (label, widget) in enumerate(fields):
            form.addWidget(QtWidgets.QLabel(label), row, 0); form.addWidget(widget, row, 1)
        form.addWidget(self.gain_slider, 3, 2)
        form.addWidget(self.agc_check, 4, 1)
        self.connection_label = QtWidgets.QLabel("")
        self.connection_label.setWordWrap(True)
        form.addWidget(self.connection_label, 0, 4, 7, 1)
        self.apply_button = QtWidgets.QPushButton("Appliquer le brouillon")
        self.apply_button.clicked.connect(self._apply_config); form.addWidget(self.apply_button, 5, 1)
        self.effective_label = QtWidgets.QLabel(""); form.addWidget(self.effective_label, 0, 3, 6, 1)
        self.device_combo = QtWidgets.QComboBox()
        self.device_combo.setToolTip("Périphérique découvert ; la sélection redémarre RX")
        self.device_combo.currentIndexChanged.connect(self._select_device)
        self.device_refresh_button = QtWidgets.QPushButton("Actualiser")
        self.device_refresh_button.clicked.connect(self._refresh_devices)
        form.addWidget(QtWidgets.QLabel("Périphérique découvert"), 6, 0)
        form.addWidget(self.device_combo, 6, 1)
        form.addWidget(self.device_refresh_button, 6, 2)
        self.antenna_combo = QtWidgets.QComboBox()
        self.antenna_combo.currentIndexChanged.connect(lambda _index: self._schedule_live_apply())
        self.antenna_label = QtWidgets.QLabel("Antenne")
        form.addWidget(self.antenna_label, 8, 0)
        form.addWidget(self.antenna_combo, 8, 1)
        self.if_gain_label = QtWidgets.QLabel("Gain IF matériel : non exposé par l'API native SDRplay")
        self.if_gain_label.setStyleSheet("color:#6b6b6b")
        form.addWidget(self.if_gain_label, 7, 0, 1, 4)
        layout.addWidget(device)
        self.extra_gains_box = QtWidgets.QGroupBox("Gains exposés par le périphérique")
        self.extra_gains_form = QtWidgets.QFormLayout(self.extra_gains_box)
        self.extra_gain_controls = {}
        layout.addWidget(self.extra_gains_box)
        scale = QtWidgets.QGroupBox("Échelle du spectre")
        scale_form = QtWidgets.QHBoxLayout(scale)
        self.y_min_spin = QtWidgets.QDoubleSpinBox(); self.y_min_spin.setRange(-240, 20); self.y_min_spin.setValue(-90); self.y_min_spin.setSuffix(" dB")
        self.y_max_spin = QtWidgets.QDoubleSpinBox(); self.y_max_spin.setRange(-100, 40); self.y_max_spin.setValue(5); self.y_max_spin.setSuffix(" dB")
        self.y_auto_button = QtWidgets.QPushButton("Réinitialiser -90…+5")
        self.y_min_spin.valueChanged.connect(self._apply_y_range); self.y_max_spin.valueChanged.connect(self._apply_y_range)
        self.y_auto_button.clicked.connect(lambda: (self.y_min_spin.setValue(-90), self.y_max_spin.setValue(5)))
        scale_form.addWidget(QtWidgets.QLabel("Bas")); scale_form.addWidget(self.y_min_spin); scale_form.addWidget(QtWidgets.QLabel("Haut")); scale_form.addWidget(self.y_max_spin); scale_form.addWidget(self.y_auto_button); scale_form.addStretch(1)
        layout.addWidget(scale)
        fft = QtWidgets.QGroupBox("Traitement d'affichage")
        fft_form = QtWidgets.QHBoxLayout(fft)
        self.fft_size_spin = QtWidgets.QSpinBox(); self.fft_size_spin.setRange(256, 16384); self.fft_size_spin.setSingleStep(256); self.fft_size_spin.setValue(4096)
        self.smoothing_spin = QtWidgets.QDoubleSpinBox(); self.smoothing_spin.setRange(0, .95); self.smoothing_spin.setSingleStep(.05); self.smoothing_spin.setValue(0); self.smoothing_spin.setToolTip("Moyenne exponentielle : 0 désactivée")
        self.fft_size_spin.valueChanged.connect(lambda value: setattr(self.spectrum, "fft_size", int(value)) if hasattr(self, "spectrum") else None)
        self.smoothing_spin.valueChanged.connect(lambda value: setattr(self.spectrum, "smoothing", float(value)) if hasattr(self, "spectrum") else None)
        fft_form.addWidget(QtWidgets.QLabel("FFT")); fft_form.addWidget(self.fft_size_spin); fft_form.addWidget(QtWidgets.QLabel("Lissage")); fft_form.addWidget(self.smoothing_spin); fft_form.addStretch(1)
        layout.addWidget(fft)
        self.normal_plot = self._new_plot(); self.normal_curve = self.normal_plot.plot(pen=pg.mkPen("#37D7FF", width=1.5))
        layout.addWidget(self.normal_plot, 1)
        return tab

    def _apply_y_range(self) -> None:
        low, high = self.y_min_spin.value(), self.y_max_spin.value()
        if high <= low:
            return
        self.normal_plot.setYRange(low, high, padding=0)
        self.compact_plot.setYRange(low, high, padding=0)

    def _sync_gain_slider(self, text: str) -> None:
        try:
            self.gain_slider.blockSignals(True)
            self.gain_slider.setValue(int(text))
        except ValueError:
            pass
        finally:
            self.gain_slider.blockSignals(False)

    def _refresh_devices(self) -> None:
        try:
            devices = self.bridge.enumerate_devices()
            current = self.bridge.device_id
            self.device_combo.blockSignals(True)
            self.device_combo.clear()
            for device in devices:
                label = device.get("label") or device.get("device_id")
                self.device_combo.addItem(f"{device.get('backend', '')}: {label}", device.get("device_id"))
            if current:
                index = self.device_combo.findData(current)
                if index >= 0:
                    self.device_combo.setCurrentIndex(index)
                try:
                    capabilities = self.bridge.capabilities(current)
                    gain_range = capabilities.get("gain_ranges", {}).get("gain_reduction_db")
                    if gain_range:
                        low, high = map(int, gain_range)
                        self.gain_slider.setRange(low, high)
                        self.gain_edit.setToolTip(f"Plage matérielle : {low}–{high} dB")
                    self.agc_check.setEnabled(bool(capabilities.get("agc_available", False)))
                    while self.extra_gains_form.rowCount():
                        self.extra_gains_form.removeRow(0)
                    self.extra_gain_controls.clear()
                    self.antenna_combo.blockSignals(True)
                    try:
                        self.antenna_combo.clear()
                        for antenna in capabilities.get("antennas", []):
                            self.antenna_combo.addItem(str(antenna), str(antenna))
                        self.antenna_label.setVisible(bool(capabilities.get("antennas", [])))
                        self.antenna_combo.setVisible(bool(capabilities.get("antennas", [])))
                        if self.bridge.config.antenna:
                            antenna_index = self.antenna_combo.findData(self.bridge.config.antenna)
                            if antenna_index >= 0:
                                self.antenna_combo.setCurrentIndex(antenna_index)
                    finally:
                        self.antenna_combo.blockSignals(False)
                    for name, bounds in capabilities.get("gain_ranges", {}).items():
                        if name == "gain_reduction_db":
                            continue
                        low, high = map(float, bounds)
                        value = float(self.bridge.config.gains.get(name, low))
                        if name.endswith("_enabled"):
                            control = QtWidgets.QCheckBox()
                            control.setChecked(bool(value))
                        elif name in {"hdr_bw", "if_type"}:
                            control = QtWidgets.QComboBox()
                            options = (("0,2 MHz", 0), ("0,5 MHz", 1), ("1,2 MHz", 2), ("1,7 MHz", 3)) if name == "hdr_bw" else (("0 kHz", 0), ("450 kHz", 1), ("1 620 kHz", 2), ("2 048 kHz", 3))
                            for label, option in options:
                                control.addItem(label, option)
                            control.setCurrentIndex(max(0, min(3, round(value))))
                        else:
                            control = QtWidgets.QSlider(QtCore.Qt.Horizontal)
                            control.setRange(round(low), round(high))
                            control.setValue(round(value))
                        labels = {
                            "bias_t_enabled": "Bias-T",
                            "rf_notch_enabled": "Notch RF",
                            "rf_dab_notch_enabled": "Filtre DAB",
                            "hdr_enabled": "HDR",
                            "hdr_bw": "Bande HDR",
                            "lna_state": "Gain RF / état LNA",
                            "if_type": "Filtre IF",
                        }
                        self.extra_gains_form.addRow(labels.get(name, name.replace("_", " ").capitalize()), control)
                        self.extra_gain_controls[name] = control
                        if isinstance(control, QtWidgets.QCheckBox):
                            control.stateChanged.connect(lambda _state, self=self: self._schedule_live_apply())
                        elif isinstance(control, QtWidgets.QComboBox):
                            control.currentIndexChanged.connect(lambda _index, self=self: self._schedule_live_apply())
                        else:
                            control.valueChanged.connect(lambda _value, self=self: self._schedule_live_apply())
                    self.extra_gains_box.setVisible(bool(self.extra_gain_controls))
                    if "if" in " ".join(self.extra_gain_controls).lower():
                        self.if_gain_label.setText("Gain IF : gRdB SDRplay (curseur ci-dessus) ; gain RF : état LNA ci-dessous")
                    else:
                        self.if_gain_label.setText("Gain IF : gRdB SDRplay (curseur ci-dessus) ; gain RF = état LNA")
                    self.device_combo.setToolTip(
                        f"Taux : {capabilities.get('sample_rates_sps', [])}; bandes : {capabilities.get('bandwidths_hz', [])}"
                    )
                except Exception:
                    pass
            self.device_combo.blockSignals(False)
        except Exception as exc:
            self.device_combo.clear(); self.device_combo.addItem(f"Découverte indisponible : {exc}")

    def _select_device(self, index: int) -> None:
        device_id = self.device_combo.itemData(index)
        if not device_id or device_id == self.bridge.device_id:
            return
        try:
            self.bridge.select_device(str(device_id))
            self._show_error("")
        except Exception as exc:
            self._show_error(f"Périphérique refusé — {exc}")
        self.refresh()

    def _streams_tab(self) -> QtWidgets.QWidget:
        tab = QtWidgets.QWidget(); layout = QtWidgets.QVBoxLayout(tab)
        self.profiles_table = QtWidgets.QTableWidget(0, 5)
        self.profiles_table.setHorizontalHeaderLabels(["Profil", "Taux", "Format", "Protocole", "Révision"])
        profiles = self.bridge.profiles.items(); self.profiles_table.setRowCount(len(profiles))
        for row, profile in enumerate(profiles):
            for column, value in enumerate((profile.name or profile.profile_id, profile.output_rate_sps, profile.sample_format.value, profile.protocol, profile.profile_revision)):
                self.profiles_table.setItem(row, column, QtWidgets.QTableWidgetItem(str(value)))
        self.profiles_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        layout.addWidget(QtWidgets.QLabel("Profils immuables publiés")); layout.addWidget(self.profiles_table)
        self.clients_table = QtWidgets.QTableWidget(0, 4)
        self.clients_table.setHorizontalHeaderLabels(["Client", "Blocs lus", "Pertes ring", "Dernière séquence"])
        self.clients_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        layout.addWidget(QtWidgets.QLabel("Sessions locales confirmées (destinations UDP séparées)")); layout.addWidget(self.clients_table)
        self.destinations_table = QtWidgets.QTableWidget(0, 8)
        self.destinations_table.setHorizontalHeaderLabels(["Destination", "Transport", "Paquets", "Octets", "Pertes file", "Erreurs", "Fréq. centrale", "Taux"])
        self.destinations_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        layout.addWidget(QtWidgets.QLabel("Destinations UDP configurées")); layout.addWidget(self.destinations_table)
        network_enabled = bool(getattr(self.runtime, "native_control", None))
        layout.addWidget(QtWidgets.QLabel("Contrôle natif loopback actif" if network_enabled else "Réseau natif désactivé par configuration"))
        return tab

    def _rf_tab(self) -> QtWidgets.QWidget:
        tab = QtWidgets.QWidget(); layout = QtWidgets.QVBoxLayout(tab)
        layout.addWidget(QtWidgets.QLabel("Aucune règle RF enregistrée. Les plages sont [min, max[ et les priorités égales qui se recouvrent sont refusées."))
        table = QtWidgets.QTableWidget(0, 6); table.setHorizontalHeaderLabels(["ID", "Min Hz", "Max Hz", "Priorité", "Antenne", "État"])
        table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch); layout.addWidget(table)
        return tab

    def _capture_tab(self) -> QtWidgets.QWidget:
        tab = QtWidgets.QWidget(); layout = QtWidgets.QFormLayout(tab)
        self.capture_path = QtWidgets.QLineEdit(str(Path.cwd() / "capture"))
        self.capture_profile = QtWidgets.QComboBox()
        for profile in self.bridge.profiles.items():
            if profile.protocol in {"ring_v2", "sdbu_v2"}:
                self.capture_profile.addItem(profile.name or profile.profile_id, (profile.profile_id, profile.profile_revision))
        self.capture_button = QtWidgets.QPushButton("Démarrer la capture")
        self.capture_button.clicked.connect(self._toggle_capture)
        self.capture_status = QtWidgets.QLabel("Recorder arrêté")
        layout.addRow("Base du fichier SigMF", self.capture_path)
        layout.addRow("Profil", self.capture_profile)
        layout.addRow(self.capture_button); layout.addRow(self.capture_status)
        layout.addRow(QtWidgets.QLabel("Une discontinuité clôt la capture ; aucun fichier existant n’est écrasé."))
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
        self.always_on_top = QtWidgets.QCheckBox("Toujours visible"); self.always_on_top.toggled.connect(self._always_on_top)
        top.addWidget(self.compact_state); top.addWidget(self.compact_frequency); top.addStretch(1); top.addWidget(self.always_on_top); top.addWidget(normal)
        layout.addLayout(top)
        self.compact_plot = self._new_plot(True); self.compact_curve = self.compact_plot.plot(pen=pg.mkPen("#37D7FF", width=1.2)); layout.addWidget(self.compact_plot)
        bottom = QtWidgets.QHBoxLayout(); self.compact_stats = QtWidgets.QLabel(""); stop = QtWidgets.QPushButton("Stop"); stop.clicked.connect(self._stop_rx)
        bottom.addWidget(self.compact_stats); bottom.addStretch(1); bottom.addWidget(stop); layout.addLayout(bottom)
        return page

    def _draw_spectrum(self, frequencies, db) -> None:
        self.normal_curve.setData(frequencies, db)
        self.compact_curve.setData(frequencies, db)

    def _stream_state(self, active: bool) -> None:
        if not active and self.bridge.running:
            self.status_bar.setText("RX active — attente de nouveaux blocs (affichage spectral en retard)")
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
            self._show_error(f"Configuration refusée — {exc}")
            self.refresh()
            return
        if self._config_apply_busy:
            # Un déplacement de slider peut produire plusieurs événements.
            # On ne garde que le dernier brouillon, jamais une file de mises
            # à jour obsolètes.
            self._config_apply_pending = requested
            return
        self._config_apply_busy = True
        self.apply_button.setEnabled(False)
        self.status_bar.setText("Mise à jour SDR à chaud…")

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
        return {
            "center_frequency_hz": int(self.frequency_edit.text()),
            "sample_rate_sps": int(self.rate_edit.text()),
            "bandwidth_hz": int(self.bandwidth_edit.text()),
            "gain_reduction_db": int(self.gain_edit.text()),
            "agc_enabled": self.agc_check.isChecked(),
            "antenna": self.antenna_combo.currentData() or None,
            "gains": {name: self._control_value(control) for name, control in self.extra_gain_controls.items()},
        }

    def _schedule_live_apply(self) -> None:
        if not getattr(self, "_live_apply_timer", None):
            return
        self._live_apply_timer.start()

    @QtCore.pyqtSlot(object, object)
    def _config_apply_finished(self, result, error) -> None:
        self._config_apply_busy = False
        self.apply_button.setEnabled(True)
        if error is None:
            self.spectrum.resync_after_reconfigure()
            self._show_error("")
        elif isinstance(error, StaleConfigError):
            self._show_error("STALE_CONFIG — les valeurs effectives ont été rechargées")
        else:
            self._show_error(f"Configuration refusée — {error}")
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
        self.apply_button.setEnabled(False)
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
            self._show_error("Recorder indisponible dans ce contexte")
            return
        try:
            if self.runtime.recorder is None:
                profile_id, revision = self.capture_profile.currentData()
                self.runtime.start_recording(self.capture_path.text(), profile_id, revision)
            else:
                self.runtime.stop_recording("arrêt opérateur")
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
        self.state_label.setText(f"RX : {state}"); self.compact_state.setText(f"RX {state}")
        color = "#157A36" if state == "RUNNING" else ("#9b1c1c" if state == "ERROR" else "#595959")
        self.state_label.setStyleSheet(f"font-weight:bold;color:{color}"); self.compact_state.setStyleSheet(f"font-weight:bold;color:{color}")
        frequency = f"{cfg['center_frequency_hz']:,} Hz".replace(",", " ")
        self.frequency_effective.setText(frequency); self.compact_frequency.setText(frequency)
        self.start_button.setText("Arrêter" if self.bridge.running else "Démarrer")
        if self.device_combo.count() == 0:
            self._refresh_devices()
        source_name = status["source"]
        if source_name.lower().startswith("source simul") or "simulat" in source_name.lower():
            self.connection_label.setText("Source active : SIMULATION déterministe\nAucun SDR physique n'est connecté.")
            self.connection_label.setStyleSheet("color:#8a5200;font-weight:bold")
        elif state == "RUNNING":
            self.connection_label.setText(f"Source active : {source_name}\nRX ouvert — périphérique : {status.get('device_id') or 'identifiant non remonté'}")
            self.connection_label.setStyleSheet("color:#157A36;font-weight:bold")
        else:
            self.connection_label.setText(f"Backend sélectionné : {source_name}\nÉtat périphérique : {state}")
            self.connection_label.setStyleSheet("color:#595959")
        disabled = state in {"OPENING", "RECONFIGURING", "STOPPING", "STARTING"}
        self.apply_button.setDisabled(disabled or self._config_apply_busy)
        self.effective_label.setText(
            f"Effectif\n{cfg['center_frequency_hz']} Hz\n{cfg['sample_rate_sps']} S/s\n{cfg['bandwidth_hz']} Hz\nRévision {cfg['revision']}"
        )
        clients = status["clients"]; self.clients_table.setRowCount(len(clients))
        for row, client in enumerate(clients):
            for column, value in enumerate((client["name"], client["blocks_read"], client["dropped_blocks"], client["last_sequence"])):
                self.clients_table.setItem(row, column, QtWidgets.QTableWidgetItem(str(value)))
        operator_udp = getattr(self.runtime, "operator_udp", None)
        destinations = [] if operator_udp is None else [operator_udp.destination.snapshot()]
        self.destinations_table.setRowCount(len(destinations))
        for row, item in enumerate(destinations):
            values = (item["destination"], item["transport"], item["sent_packets"], item["sent_bytes"], item["dropped_blocks"], item["socket_errors"], item.get("last_center_frequency_hz") or "—", item.get("last_sample_rate_sps") or "—")
            for column, value in enumerate(values):
                self.destinations_table.setItem(row, column, QtWidgets.QTableWidgetItem(str(value)))
        self.status_bar.setText(f"{status['sample_rate_measured']/1e6:.3f} MS/s | pertes source queue {status['source_queue_drops']} | erreurs {status['source_errors']}")
        self.compact_stats.setText(f"{len(clients)} clients | pertes {status['source_queue_drops']}")
        recorder = getattr(self.runtime, "recorder", None)
        if recorder:
            self.capture_status.setText(f"Capture active — {recorder.bytes_written} octets")
            self.capture_button.setText("Arrêter la capture")
        else:
            self.capture_status.setText("Recorder arrêté")
            self.capture_button.setText("Démarrer la capture")
        diagnostics = {key: status[key] for key in ("state", "source", "source_id", "epoch", "blocks_received", "blocks_written", "source_queue_drops", "source_queue_capacity", "source_queue_high_water", "source_errors", "last_error", "pipelines")}
        import json
        self.diagnostics.setPlainText(json.dumps(diagnostics, ensure_ascii=False, indent=2))

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        recorder_active = bool(getattr(self.runtime, "recorder", None))
        if self.bridge.running or recorder_active:
            answer = QtWidgets.QMessageBox.question(self, "Quitter SDRbridge", "Arrêter la réception et quitter ?", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Cancel)
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
