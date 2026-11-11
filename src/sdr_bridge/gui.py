from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys
import threading
import time
from typing import Any

import numpy as np
import pyqtgraph as pg
from PyQt5 import QtCore, QtGui, QtWidgets

from .bridge import SDRBridge, StaleConfigError
from . import __version__
from .dsp import payload_to_complex
from .diagnostics import export_diagnostic_bundle
from .frequency_control import FrequencyControlWidget
from .gui_theme import DARK_STYLESHEET, SDRBridgeProxyStyle
from .model import MAX_CENTER_FREQUENCY_HZ, LifecycleState
from .recording import CaptureFormat
from .rf_profiles import RFProfileSet, RFRule


logger = logging.getLogger(__name__)


TEXT = {
    "en": {
        "radio": "Radio", "clients": "Clients & Streams", "rf_profiles": "RF Profiles", "captures": "Captures",
        "acquisition_active": "Acquisition active", "acquisition_stopped": "Acquisition stopped",
        "acquisition_starting": "Acquisition starting…", "acquisition_stopping": "Acquisition stopping…",
        "source": "Source", "measured_rate": "Measured rate", "active_consumers": "Active consumers",
        "udp_throughput": "Useful UDP rate", "losses": "Losses", "top_losses": "Total losses", "no_loss": "0 reported loss",
        "process_cpu": "SDRbridge CPU", "process_cpu_value": "{cores:.2f} / {capacity} cores",
        "process_cpu_tip": "CPU used by the SDRbridge process only, shown as logical cores used / available. A plateau combined with rising losses indicates CPU saturation.",
        "receiver": "RECEIVER · HARDWARE SETTINGS", "source_sdr": "SDR source", "sampling": "Sampling rate",
        "bandwidth": "Bandwidth", "bandwidth_auto": "Auto — {value:.3f} MHz",
        "bandwidth_unavailable": "Not adjustable by this receiver",
        "bandwidth_tip": "Hardware tuner/IF filter. Auto selects the hardware value closest to the IQ sampling rate.",
        "antenna": "Antenna", "if_gain": "IF gain", "rf_gain": "RF gain",
        "auto_rf": "Auto RF profile", "configure_rf": "Configure RF rules →", "rf_analysis": "RF ANALYSIS",
        "spectrum": "Spectrum", "waterfall": "Waterfall", "split": "Split", "diagnostics": "Diagnostics…",
        "settings": "Settings", "help": "Help…", "about": "About", "language": "Language", "always_on_top": "Always on top",
        "close": "Close", "apply": "Apply", "copy_json": "Copy JSON", "export_diagnostics": "Export report ZIP…", "open_folder": "Open folder ↗",
        "recording_config": "RECORDING CONFIGURATION", "format": "Format", "iq_profile": "IQ profile",
        "output_file": "Output file", "start_capture": "Choose file and start capture…", "stop_capture": "Stop capture",
        "recorder_stopped": "Recorder stopped", "recording_active": "Recording active", "recorded_volume": "Recorded volume",
        "recorded_source": "Recorded source", "integrity": "Integrity", "source_errors": "source errors",
        "destinations": "DESTINATIONS AND CONSUMERS", "add_udp": "+ Add UDP client", "refresh": "Refresh",
        "endpoint": "Endpoint", "protocol": "Protocol", "target_rate": "Target rate", "datagram": "Datagram",
        "queue": "Queue", "create_stream": "Create stream", "update_stream": "Update selected", "remove": "Remove",
        "rf_rules": "BAND RULES", "new_rule": "+ New rule", "automatic_mode": "AUTOMATIC MODE",
        "auto_enabled": "Automatic profiles enabled", "manual_override": "Manual override active", "resume_auto": "Resume AUTO",
        "no_rules": "No RF rules registered", "edit_rule": "Edit RF rule", "add_rule": "New RF rule",
        "center_frequency": "SDR CENTER FREQUENCY", "loop_iq_file": "Loop IQ file",
        "refresh_sources": "Refresh sources", "open_iq_file": "Open an IQ recording",
        "compact_view": "Compact view", "normal_view": "Normal view", "start_stop_sdr": "Start or stop SDR",
        "start_sdr": "Start SDR", "stop_sdr": "Stop SDR",
        "smoothing": "Smoothing", "smoothing_tip": "Exponential average: 0 disables smoothing",
        "power_dbfs": "Power (dBFS)", "frequency_offset": "Frequency offset", "absolute_frequency": "Frequency (MHz)", "history": "History",
        "logical_iq_rate": "Logical IQ rate", "measured_network_rate": "Measured network rate",
        "consumer_destination": "Consumer / destination", "type": "Type", "rate": "Rate",
        "packets_blocks": "Packets / blocks", "status": "Status", "profile": "Profile",
        "revision": "Revision", "client": "Client", "blocks_read": "Blocks read",
        "ring_drops": "Ring drops", "last_sequence": "Last sequence", "destination": "Destination",
        "transport": "Transport", "output_rate": "Output rate", "packets": "Packets", "bytes": "Bytes",
        "queue_drops": "Queue drops", "errors": "Errors", "center_hz": "Center Hz",
        "udp_editor": "UDP STREAM EDITOR", "udp_note": "Each UDP destination has its own effective rate. Equal rates share one DSP pipeline. QMAP/Linrad is fixed at 96 kS/s (usual port 50004).",
        "lan_udp_enabled": "LAN UDP destinations enabled", "lan_udp_disabled": "LAN UDP destinations disabled — enable in Settings",
        "edit": "Edit", "rule": "Rule", "min_mhz": "Min MHz", "max_mhz": "Max MHz",
        "priority": "Priority", "state": "State", "hysteresis": "Hysteresis", "agc": "AGC", "if_rf": "IF / RF",
        "rf_note": "Ranges use [minimum, maximum[. Overlapping enabled rules need different priorities; hysteresis prevents profile chatter at a boundary.",
        "keep": "keep", "enabled": "enabled", "disabled": "disabled", "active_upper": "ACTIVE",
        "capture_note": "A native Save As dialog opens before recording. Files are never overwritten; a discontinuity closes the capture.",
        "system_diagnostics": "SYSTEM DIAGNOSTICS", "diagnostics_title": "SDRbridge diagnostics",
        "if_gain_reduction": "IF gain · reduction", "rf_gain_reduction": "RF gain · LNA reduction",
        "reduction_value": "{value:g} dB red.", "lna_state_value": "state {value:g}",
        "reported_losses": "{count} reported", "consumers_count": "{count} consumers",
        "compact_stats": "{count} consumers | drops {drops}",
        "status_line": "{rate:.3f} MS/s | processing drops {drops} | errors {errors}",
        "local": "Local", "active": "active", "idle": "idle", "streaming": "streaming",
        "capture_active": "Capture active — {bytes} bytes — {file}", "losses_count": "{count} losses",
        "top": "Top", "iq_file": "IQ FILE", "simulation": "SIMULATION", "select_iq_recording": "Select an IQ recording",
        "rx_waiting": "RX active — waiting for new blocks (spectrum display delayed)",
        "format_filter": "IQ recordings (*.wav *.rf64);;WAVE files (*.wav);;All files (*.*)",
        "browse_iq_source": "IQ file… — Browse", "blocks_suffix": " blocks",
        "sdrpp_raw": "SDR++ raw CS16", "sdrpp_wav": "SDR++ WAV — int16 stereo IQ",
        "hdsdr_wav": "HDSDR WAV — int16 stereo IQ + auxi", "applying_update": "Applying hot SDR update…",
        "bias_t": "Bias-T", "fm_notch": "FM Notch", "dab_notch": "DAB Notch", "hdr": "HDR", "hdr_bandwidth": "HDR bandwidth", "if_filter": "IF filter",
        "rx_only_bridge": "RX-only IQ bridge", "authors": "Authors", "gui_concept": "GUI v0.7 dark concept",
        "license_summary": "GNU GPL v3 or later — no warranty", "source_code": "Source code: https://github.com/stephanerey/SDRbridge",
        "diagnostics_exported": "Diagnostic report exported to:\n{path}", "diagnostics_export_failed": "Diagnostic export failed — {error}",
        "save_diagnostics": "Save SDRbridge diagnostic report",
        "display_min": "Min", "display_max": "Max",
        "cancel": "Cancel", "save": "Save", "save_capture": "Save IQ capture",
        "sigmf_filter": "SigMF metadata (*.sigmf-meta)", "wave_iq_filter": "WAVE IQ recordings (*.wav)",
        "hardware_controls_unavailable": "Hardware controls unavailable — {error}", "discovery_unavailable": "Discovery unavailable: {error}",
        "device_rejected": "Device rejected — {error}", "iq_selection_unavailable": "IQ file selection is unavailable",
        "iq_file_rejected": "IQ file rejected — {error}", "udp_management_unavailable": "UDP destination management is unavailable",
        "udp_update_unavailable": "UDP destination update is unavailable", "select_udp_first": "Select a UDP client first",
        "endpoint_immutable": "Endpoint cannot be changed in-place; remove it and add the new endpoint",
        "client_rejected": "Client rejected — {error}", "client_update_failed": "Client update failed — {error}",
        "client_removal_failed": "Client removal failed — {error}", "rf_rule_rejected": "RF rule rejected — {error}",
        "configuration_rejected": "Configuration rejected — {error}", "stale_config": "STALE_CONFIG — effective values were reloaded",
        "recorder_unavailable": "Recorder unavailable in this context", "quit_title": "Quit SDRbridge",
        "quit_question": "Stop reception and quit?", "quit_confirm": "Stop and quit", "shutting_down": "shutting down…",
        "shutdown_failed": "Shutdown failed — {error}",
    },
    "fr": {
        "radio": "Radio", "clients": "Clients et flux", "rf_profiles": "Profils RF", "captures": "Captures",
        "acquisition_active": "Acquisition active", "acquisition_stopped": "Acquisition arrêtée",
        "acquisition_starting": "Démarrage de l’acquisition…", "acquisition_stopping": "Arrêt de l’acquisition…",
        "source": "Source", "measured_rate": "Débit mesuré", "active_consumers": "Consommateurs actifs",
        "udp_throughput": "Débit UDP utile", "losses": "Pertes", "top_losses": "Pertes totales", "no_loss": "0 perte déclarée",
        "process_cpu": "CPU SDRbridge", "process_cpu_value": "{cores:.2f} / {capacity} cores",
        "process_cpu_tip": "CPU utilisé uniquement par le processus SDRbridge, exprimé en cœurs logiques utilisés / disponibles. Un plateau accompagné de pertes croissantes indique une saturation CPU.",
        "receiver": "RÉCEPTEUR · RÉGLAGES MATÉRIELS", "source_sdr": "Source SDR", "sampling": "Débit d'échantillonnage",
        "bandwidth": "Bande passante", "bandwidth_auto": "Auto — {value:.3f} MHz",
        "bandwidth_unavailable": "Non réglable par ce récepteur",
        "bandwidth_tip": "Filtre matériel du tuner/IF. Auto choisit la valeur matérielle la plus proche du débit d’échantillonnage IQ.",
        "antenna": "Antenne", "if_gain": "Gain IF", "rf_gain": "Gain RF",
        "auto_rf": "Profil RF automatique", "configure_rf": "Configurer les règles RF →", "rf_analysis": "ANALYSE RF",
        "spectrum": "Spectre", "waterfall": "Cascade", "split": "Partagé", "diagnostics": "Diagnostics…",
        "settings": "Paramètres", "help": "Aide…", "about": "À propos", "language": "Langue", "always_on_top": "Toujours au-dessus",
        "close": "Fermer", "apply": "Appliquer", "copy_json": "Copier le JSON", "export_diagnostics": "Exporter le rapport ZIP…", "open_folder": "Ouvrir le dossier ↗",
        "recording_config": "CONFIGURATION DE L'ENREGISTREMENT", "format": "Format", "iq_profile": "Profil IQ",
        "output_file": "Fichier de sortie", "start_capture": "Choisir le fichier et démarrer…", "stop_capture": "Arrêter la capture",
        "recorder_stopped": "Enregistreur arrêté", "recording_active": "Enregistrement actif", "recorded_volume": "Volume enregistré",
        "recorded_source": "Source enregistrée", "integrity": "Intégrité", "source_errors": "erreurs source",
        "destinations": "DESTINATIONS ET CONSOMMATEURS", "add_udp": "+ Ajouter client UDP", "refresh": "Actualiser",
        "endpoint": "Destination", "protocol": "Protocole", "target_rate": "Débit cible", "datagram": "Datagramme",
        "queue": "File", "create_stream": "Créer le flux", "update_stream": "Modifier la sélection", "remove": "Supprimer",
        "rf_rules": "RÈGLES PAR BANDE", "new_rule": "+ Nouvelle règle", "automatic_mode": "MODE AUTOMATIQUE",
        "auto_enabled": "Profils automatiques actifs", "manual_override": "Override manuel actif", "resume_auto": "Reprendre AUTO",
        "no_rules": "Aucune règle RF enregistrée", "edit_rule": "Modifier la règle RF", "add_rule": "Nouvelle règle RF",
        "center_frequency": "FRÉQUENCE CENTRALE SDR", "loop_iq_file": "Lire le fichier IQ en boucle",
        "refresh_sources": "Actualiser les sources", "open_iq_file": "Ouvrir un enregistrement IQ",
        "compact_view": "Vue compacte", "normal_view": "Vue normale", "start_stop_sdr": "Démarrer ou arrêter le SDR",
        "start_sdr": "Démarrer le SDR", "stop_sdr": "Arrêter le SDR",
        "smoothing": "Lissage", "smoothing_tip": "Moyenne exponentielle : 0 désactive le lissage",
        "power_dbfs": "Puissance (dBFS)", "frequency_offset": "Décalage de fréquence", "absolute_frequency": "Fréquence (MHz)", "history": "Historique",
        "logical_iq_rate": "Débit IQ logique", "measured_network_rate": "Débit réseau mesuré",
        "consumer_destination": "Consommateur / destination", "type": "Type", "rate": "Débit",
        "packets_blocks": "Paquets / blocs", "status": "État", "profile": "Profil",
        "revision": "Révision", "client": "Client", "blocks_read": "Blocs lus",
        "ring_drops": "Pertes anneau", "last_sequence": "Dernière séquence", "destination": "Destination",
        "transport": "Transport", "output_rate": "Débit de sortie", "packets": "Paquets", "bytes": "Octets",
        "queue_drops": "Pertes de file", "errors": "Erreurs", "center_hz": "Fréquence centrale (Hz)",
        "udp_editor": "ÉDITEUR DE FLUX UDP", "udp_note": "Chaque destination UDP possède son propre débit effectif. Les débits identiques partagent une chaîne DSP. QMAP/Linrad est fixé à 96 kS/s (port habituel 50004).",
        "lan_udp_enabled": "Destinations UDP LAN autorisées", "lan_udp_disabled": "Destinations UDP LAN désactivées — activer dans Paramètres",
        "edit": "Modifier", "rule": "Règle", "min_mhz": "Min MHz", "max_mhz": "Max MHz",
        "priority": "Priorité", "state": "État", "hysteresis": "Hystérésis", "agc": "AGC", "if_rf": "IF / RF",
        "rf_note": "Les plages utilisent [minimum, maximum[. Les règles actives qui se chevauchent doivent avoir des priorités différentes ; l’hystérésis évite les basculements à une limite.",
        "keep": "conserver", "enabled": "active", "disabled": "désactivée", "active_upper": "ACTIVE",
        "capture_note": "Une boîte de dialogue Enregistrer sous s’ouvre avant l’enregistrement. Les fichiers ne sont jamais écrasés ; une discontinuité ferme la capture.",
        "system_diagnostics": "DIAGNOSTICS SYSTÈME", "diagnostics_title": "Diagnostics SDRbridge",
        "if_gain_reduction": "Gain IF · atténuation", "rf_gain_reduction": "Gain RF · atténuation LNA",
        "reduction_value": "{value:g} dB réd.", "lna_state_value": "état {value:g}",
        "reported_losses": "{count} déclarée(s)", "consumers_count": "{count} consommateur(s)",
        "compact_stats": "{count} consommateur(s) | pertes {drops}",
        "status_line": "{rate:.3f} MS/s | pertes de traitement {drops} | erreurs {errors}",
        "local": "Local", "active": "actif", "idle": "inactif", "streaming": "en cours",
        "capture_active": "Capture active — {bytes} octets — {file}", "losses_count": "{count} perte(s)",
        "top": "Dessus", "iq_file": "FICHIER IQ", "simulation": "SIMULATION", "select_iq_recording": "Sélectionner un enregistrement IQ",
        "rx_waiting": "RX actif — attente de nouveaux blocs (affichage du spectre retardé)",
        "format_filter": "Enregistrements IQ (*.wav *.rf64);;Fichiers WAVE (*.wav);;Tous les fichiers (*.*)",
        "browse_iq_source": "Fichier IQ… — Parcourir", "blocks_suffix": " blocs",
        "sdrpp_raw": "SDR++ CS16 brut", "sdrpp_wav": "SDR++ WAV — IQ stéréo int16",
        "hdsdr_wav": "HDSDR WAV — IQ stéréo int16 + auxi", "applying_update": "Application des réglages SDR…",
        "bias_t": "Bias-T", "fm_notch": "Filtre FM", "dab_notch": "Filtre DAB", "hdr": "HDR", "hdr_bandwidth": "Bande passante HDR", "if_filter": "Filtre IF",
        "rx_only_bridge": "Passerelle IQ en réception uniquement", "authors": "Auteurs", "gui_concept": "Interface sombre v0.7",
        "license_summary": "GNU GPL v3 ou ultérieure — sans garantie", "source_code": "Code source : https://github.com/stephanerey/SDRbridge",
        "diagnostics_exported": "Rapport de diagnostic exporté vers :\n{path}", "diagnostics_export_failed": "Échec de l’export des diagnostics — {error}",
        "save_diagnostics": "Enregistrer le rapport de diagnostic SDRbridge",
        "display_min": "Min", "display_max": "Max",
        "cancel": "Annuler", "save": "Enregistrer", "save_capture": "Enregistrer la capture IQ",
        "sigmf_filter": "Métadonnées SigMF (*.sigmf-meta)", "wave_iq_filter": "Enregistrements IQ WAVE (*.wav)",
        "hardware_controls_unavailable": "Contrôles matériels indisponibles — {error}", "discovery_unavailable": "Découverte indisponible : {error}",
        "device_rejected": "Périphérique refusé — {error}", "iq_selection_unavailable": "La sélection d’un fichier IQ est indisponible",
        "iq_file_rejected": "Fichier IQ refusé — {error}", "udp_management_unavailable": "La gestion des destinations UDP est indisponible",
        "udp_update_unavailable": "La modification des destinations UDP est indisponible", "select_udp_first": "Sélectionnez d’abord un client UDP",
        "endpoint_immutable": "La destination ne peut pas être modifiée directement ; supprimez-la puis ajoutez la nouvelle destination",
        "client_rejected": "Client refusé — {error}", "client_update_failed": "Échec de modification du client — {error}",
        "client_removal_failed": "Échec de suppression du client — {error}", "rf_rule_rejected": "Règle RF refusée — {error}",
        "configuration_rejected": "Configuration refusée — {error}", "stale_config": "STALE_CONFIG — les valeurs effectives ont été rechargées",
        "recorder_unavailable": "Enregistreur indisponible dans ce contexte", "quit_title": "Quitter SDRbridge",
        "quit_question": "Arrêter la réception et quitter ?", "quit_confirm": "Arrêter et quitter", "shutting_down": "fermeture en cours…",
        "shutdown_failed": "Échec de l’arrêt — {error}",
    },
}


class AbsoluteFrequencyAxis(pg.AxisItem):
    """Render FFT offset coordinates as absolute MHz around the effective VFO."""

    def __init__(self, *args, center_frequency_hz: int = 0, **kwargs):
        super().__init__(*args, **kwargs)
        self.center_frequency_hz = int(center_frequency_hz)

    def set_center_frequency(self, center_frequency_hz: int) -> None:
        center_frequency_hz = int(center_frequency_hz)
        if center_frequency_hz == self.center_frequency_hz:
            return
        self.center_frequency_hz = center_frequency_hz
        self.picture = None
        self.update()

    def tickStrings(self, values: list[float], scale: float, spacing: float) -> list[str]:
        center_mhz = self.center_frequency_hz / 1_000_000.0
        return [f"{center_mhz + float(value) * scale:.4f}" for value in values]


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, language: str, always_on_top: bool, parent=None, *, lan_udp_enabled: bool = False):
        super().__init__(parent)
        french = language == "fr"
        self.setWindowTitle("Paramètres SDRbridge" if french else "SDRbridge settings")
        self.setMinimumWidth(360)
        form = QtWidgets.QFormLayout(self)
        self.language_combo = QtWidgets.QComboBox()
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("Français", "fr")
        self.language_combo.setCurrentIndex(max(0, self.language_combo.findData(language)))
        self.always_check = QtWidgets.QCheckBox()
        self.always_check.setChecked(always_on_top)
        self.lan_udp_check = QtWidgets.QCheckBox()
        self.lan_udp_check.setChecked(lan_udp_enabled)
        self.lan_udp_note = QtWidgets.QLabel(
            "Autorise uniquement les destinations IQ UDP saisies localement ; le contrôle RF reste local."
            if french else
            "Allows only locally entered IQ UDP destinations; RF control remains local."
        )
        self.lan_udp_note.setWordWrap(True)
        self.lan_udp_note.setProperty("role", "muted")
        form.addRow("Langue" if french else "Language", self.language_combo)
        form.addRow("Toujours au-dessus" if french else "Always on top", self.always_check)
        form.addRow("Autoriser UDP LAN" if french else "Allow LAN UDP destinations", self.lan_udp_check)
        form.addRow("", self.lan_udp_note)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.button(QtWidgets.QDialogButtonBox.Cancel).setText("Annuler" if french else "Cancel")
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        form.addRow(buttons)


class RFRuleDialog(QtWidgets.QDialog):
    def __init__(self, capabilities: dict, device_id: str | None, rule: RFRule | None = None, parent=None, language: str = "en"):
        super().__init__(parent)
        french = language == "fr"
        translated = {
            "edit": "Modifier la règle RF" if french else "Edit RF rule",
            "new": "Nouvelle règle RF" if french else "New RF rule",
            "keep": "Conserver" if french else "Keep current",
            "profile": "Nom du profil" if french else "Profile name",
            "minimum": "Minimum",
            "maximum": "Maximum (exclu)" if french else "Maximum (exclusive)",
            "priority": "Priorité" if french else "Priority",
            "hysteresis": "Hystérésis" if french else "Hysteresis",
            "antenna": "Antenne" if french else "Antenna",
            "bandwidth": "Bande passante" if french else "Bandwidth",
            "enabled": "Activée" if french else "Enabled",
            "if_gain": "Gain IF · atténuation" if french else "IF gain · reduction",
            "rf_gain": "Gain RF · atténuation LNA" if french else "RF gain · LNA reduction",
        }
        self._rule_id = rule.rule_id if rule else None
        self._device_id = device_id
        self.setWindowTitle(translated["edit"] if rule else translated["new"])
        self.setMinimumWidth(520)
        form = QtWidgets.QFormLayout(self)
        self.name_edit = QtWidgets.QLineEdit(rule.rule_id if rule else "")
        self.min_spin = QtWidgets.QDoubleSpinBox(); self.min_spin.setRange(.001, 2_000); self.min_spin.setDecimals(6); self.min_spin.setSuffix(" MHz")
        self.max_spin = QtWidgets.QDoubleSpinBox(); self.max_spin.setRange(.001, 2_000); self.max_spin.setDecimals(6); self.max_spin.setSuffix(" MHz")
        self.min_spin.setValue((rule.min_hz if rule else 144_000_000) / 1e6)
        self.max_spin.setValue((rule.max_hz if rule else 146_000_000) / 1e6)
        self.priority_spin = QtWidgets.QSpinBox(); self.priority_spin.setRange(-1000, 1000); self.priority_spin.setValue(rule.priority if rule else 10)
        self.hysteresis_spin = QtWidgets.QDoubleSpinBox(); self.hysteresis_spin.setRange(0, 10_000); self.hysteresis_spin.setDecimals(1); self.hysteresis_spin.setSuffix(" kHz"); self.hysteresis_spin.setValue((rule.hysteresis_hz if rule else 0) / 1000)
        self.antenna_combo = QtWidgets.QComboBox(); self.antenna_combo.addItem("—", None)
        for antenna in capabilities.get("antennas", ()):
            self.antenna_combo.addItem(str(antenna), str(antenna))
        if rule and rule.antenna is not None:
            self.antenna_combo.setCurrentIndex(max(0, self.antenna_combo.findData(rule.antenna)))
        self.bandwidth_combo = QtWidgets.QComboBox(); self.bandwidth_combo.addItem("—", None)
        for bandwidth in capabilities.get("bandwidths_hz", ()):
            self.bandwidth_combo.addItem(f"{int(bandwidth) / 1e6:.3f} MHz", int(bandwidth))
        if rule and rule.bandwidth_hz is not None:
            self.bandwidth_combo.setCurrentIndex(max(0, self.bandwidth_combo.findData(rule.bandwidth_hz)))
        self.agc_combo = QtWidgets.QComboBox(); self.agc_combo.addItem(translated["keep"], None); self.agc_combo.addItem("ON", True); self.agc_combo.addItem("OFF", False)
        if rule and rule.agc_enabled is not None:
            self.agc_combo.setCurrentIndex(1 if rule.agc_enabled else 2)
        self.gain_inputs: dict[str, QtWidgets.QDoubleSpinBox] = {}
        gain_values = capabilities.get("gain_values", {})
        for name, bounds in capabilities.get("gain_ranges", {}).items():
            low, high = map(float, bounds)
            control = QtWidgets.QDoubleSpinBox(); control.setRange(low, high); control.setDecimals(2)
            control.setSingleStep(float(capabilities.get("gain_steps", {}).get(name, 1.0) or 1.0))
            control.setSuffix(" dB" if name.upper() == "IFGR" else "")
            control.setValue(float((rule.gains if rule else {}).get(name, gain_values.get(name, low))))
            self.gain_inputs[name] = control
        self.enabled_check = QtWidgets.QCheckBox(); self.enabled_check.setChecked(rule.enabled if rule else True)
        for label, widget in (
            (translated["profile"], self.name_edit), (translated["minimum"], self.min_spin), (translated["maximum"], self.max_spin),
            (translated["priority"], self.priority_spin), (translated["hysteresis"], self.hysteresis_spin), (translated["antenna"], self.antenna_combo),
            (translated["bandwidth"], self.bandwidth_combo), ("AGC", self.agc_combo),
        ):
            form.addRow(label, widget)
        for name, control in self.gain_inputs.items():
            label = {"IFGR": translated["if_gain"], "RFGR": translated["rf_gain"]}.get(name.upper(), name)
            form.addRow(label, control)
        form.addRow(translated["enabled"], self.enabled_check)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        buttons.button(QtWidgets.QDialogButtonBox.Save).setText("Enregistrer" if french else "Save")
        buttons.button(QtWidgets.QDialogButtonBox.Cancel).setText("Annuler" if french else "Cancel")
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addRow(buttons)

    def rule(self) -> RFRule:
        rule_id = self.name_edit.text().strip()
        if not rule_id:
            raise ValueError("profile name is required")
        min_hz = round(self.min_spin.value() * 1e6)
        max_hz = round(self.max_spin.value() * 1e6)
        gains = {name: control.value() for name, control in self.gain_inputs.items()}
        return RFRule(
            rule_id, min_hz, max_hz, self.priority_spin.value(), self.enabled_check.isChecked(),
            self._device_id, self.antenna_combo.currentData(), gains, self.agc_combo.currentData(),
            self.bandwidth_combo.currentData(), round(self.hysteresis_spin.value() * 1000),
        )


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
        # Ten display frames per second are sufficient for an operator
        # waterfall and leave deterministic CPU/GIL headroom for 10 MS/s DSP.
        self.timer.setInterval(100)
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
        length = min(self.fft_size, latest.sample_count)
        if length < 8:
            return
        # The display consumes only one FFT window.  Converting the complete
        # 32768-sample acquisition block here needlessly allocated and scaled
        # eight times more data for the default 4096-point FFT, competing with
        # the real-time DSP worker at 8-10 MS/s.
        display_bytes = length * latest.sample_format.bytes_per_iq
        samples = payload_to_complex(latest.payload[:display_bytes], latest.sample_format)
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
        frequencies = np.fft.fftshift(np.fft.fftfreq(length, 1 / latest.sample_rate_sps)) / 1_000_000.0
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
    rxActionFinished = QtCore.pyqtSignal(object)
    IQ_FILE_PICKER = "__browse_iq_file__"
    BANDWIDTH_AUTO_ROLE = QtCore.Qt.UserRole + 1
    NORMAL_LEFT_AXIS_WIDTH = 58

    def __init__(self, bridge: SDRBridge, runtime: Any | None = None):
        super().__init__()
        self.bridge = bridge
        self.runtime = runtime
        self._normal_geometry: QtCore.QByteArray | None = None
        self._config_apply_busy = False
        self._config_apply_pending: dict | None = None
        self._rx_action_busy = False
        self._rx_action_target_running: bool | None = None
        self._capability_refresh_attempts = 0
        self._capabilities: dict[str, Any] = {}
        self._bandwidth_auto = True
        self._waterfall_rows = 180
        self._waterfall: np.ndarray | None = None
        self._plot_mode = "spectrum"
        self._last_udp_total = 0
        self._last_udp_sample_at = time.monotonic()
        self._udp_wire_rate_bps = 0.0
        self._last_cpu_process = time.process_time()
        self._last_cpu_wall = time.monotonic()
        self._process_cpu_percent = 0.0
        self._logical_cpu_count = max(1, os.cpu_count() or 1)
        self._active_rf_rule_id: str | None = None
        self._applying_rf_profile = False
        self._primary_gain_names: list[str | None] = [None, None]
        self.rf_profiles = RFProfileSet()
        self._gain_table: list[tuple[int, int, int, int]] = [
            (1_000, 30_000_000, 40, 0),
            (30_000_000, 2_000_000_001, 40, 0),
        ]
        self._live_apply_timer = QtCore.QTimer(self)
        self._live_apply_timer.setSingleShot(True)
        self._live_apply_timer.setInterval(180)
        self._live_apply_timer.timeout.connect(self._apply_config)
        self.configApplied.connect(self._config_apply_finished)
        self.rxActionFinished.connect(self._rx_action_finished)
        instance_name = getattr(runtime, "instance_name", "default") if runtime is not None else "default"
        self._settings = (
            QtCore.QSettings("SDRbridge", f"SDRbridge-{instance_name}")
            if runtime is not None else None
        )
        if self._settings is not None:
            self._bandwidth_auto = bool(int(self._settings.value("bandwidth_auto", 1)))
        default_language = "fr" if QtCore.QLocale.system().language() == QtCore.QLocale.French else "en"
        self.language = str(self._settings.value("language", default_language) if self._settings else "en")
        if self.language not in TEXT:
            self.language = "en"
        if self._settings is not None and int(self._settings.value("plot_mode_default_revision", 0)) < 1:
            # One-time migration from the former Spectrum default. Later
            # operator selections remain persistent as before.
            self._plot_mode = "waterfall"
            self._settings.setValue("plot_mode", self._plot_mode)
            self._settings.setValue("plot_mode_default_revision", 1)
            self._settings.sync()
        else:
            self._plot_mode = str(self._settings.value("plot_mode", "waterfall") if self._settings else "waterfall")
        if self._plot_mode not in {"spectrum", "waterfall", "split"}:
            self._plot_mode = "spectrum"
        self._load_rf_profiles()
        self.setWindowTitle(f"SDRbridge {__version__} — RX — {instance_name}")
        self.setStyleSheet(DARK_STYLESHEET)
        self.resize(1280, 800)
        self.setMinimumSize(980, 640)
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

    def _t(self, key: str) -> str:
        return TEXT.get(self.language, TEXT["en"]).get(key, TEXT["en"].get(key, key))

    @staticmethod
    def _card(layout: QtWidgets.QLayout | None = None) -> QtWidgets.QFrame:
        frame = QtWidgets.QFrame()
        frame.setProperty("card", True)
        if layout is not None:
            frame.setLayout(layout)
        return frame

    def _metric_card(self, title_key: str) -> tuple[QtWidgets.QFrame, QtWidgets.QLabel, QtWidgets.QLabel]:
        layout = QtWidgets.QVBoxLayout(); layout.setContentsMargins(12, 7, 12, 7); layout.setSpacing(2)
        title = QtWidgets.QLabel(self._t(title_key)); title.setProperty("role", "metricTitle")
        value = QtWidgets.QLabel("—"); value.setProperty("role", "metricValue")
        layout.addWidget(title); layout.addWidget(value)
        card = self._card(layout); card.setMinimumWidth(132); card.setMaximumHeight(58)
        return card, title, value

    def _update_process_cpu_metric(self) -> float:
        """Sample CPU time for this process, normalized so 100% is one core."""
        wall_now = time.monotonic()
        process_now = time.process_time()
        elapsed = wall_now - self._last_cpu_wall
        if elapsed >= 0.25:
            process_elapsed = max(0.0, process_now - self._last_cpu_process)
            self._process_cpu_percent = 100.0 * process_elapsed / elapsed
        self._last_cpu_wall = wall_now
        self._last_cpu_process = process_now
        self.cpu_label.setText(self._t("process_cpu_value").format(
            percent=self._process_cpu_percent,
            cores=self._process_cpu_percent / 100.0,
            capacity=self._logical_cpu_count,
        ))
        return self._process_cpu_percent

    def _load_rf_profiles(self) -> None:
        if self._settings is None:
            return
        try:
            raw = json.loads(str(self._settings.value("rf_rules", "[]")))
            self.rf_profiles = RFProfileSet(RFRule.from_dict(item) for item in raw)
            if not bool(int(self._settings.value("rf_auto_enabled", 1))):
                self.rf_profiles.suspend_manual()
        except Exception:
            self.rf_profiles = RFProfileSet()

    def _save_rf_profiles(self) -> None:
        if self._settings is None:
            return
        self._settings.setValue("rf_rules", json.dumps([rule.to_dict() for rule in self.rf_profiles.rules], ensure_ascii=False))
        self._settings.setValue("rf_auto_enabled", 0 if self.rf_profiles.suspended else 1)
        self._settings.sync()

    def _open_settings(self) -> None:
        dialog = SettingsDialog(
            self.language,
            bool(self.windowFlags() & QtCore.Qt.WindowStaysOnTopHint),
            self,
            lan_udp_enabled=bool(getattr(self.runtime, "lan_udp_enabled", False)),
        )
        dialog.setStyleSheet(DARK_STYLESHEET)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        if self.runtime is not None and hasattr(self.runtime, "set_lan_udp_enabled"):
            try:
                self._lan_udp_enabled = bool(self.runtime.set_lan_udp_enabled(dialog.lan_udp_check.isChecked()))
            except Exception as exc:
                self._show_error(self._t("configuration_rejected").format(error=exc))
                return
        self.language = str(dialog.language_combo.currentData())
        self._always_on_top(dialog.always_check.isChecked())
        if self._settings is not None:
            self._settings.setValue("language", self.language); self._settings.sync()
        self._retranslate_ui()

    def _open_about(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "SDRbridge",
            f"SDRbridge {__version__}\n{self._t('rx_only_bridge')}\n\n"
            f"{self._t('authors')}\n"
            "Stephane REY F1TJJ\n"
            "Philippe Borghini F5JWF\n\n"
            f"Copyright © 2026\n{self._t('license_summary')}\n"
            f"{self._t('source_code')}\n\n" + self._t("gui_concept"),
        )

    def _open_help(self) -> None:
        filename = "HELP_FR.md" if self.language == "fr" else "HELP_EN.md"
        candidates = []
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS) / "docs" / filename)
        candidates.append(Path(__file__).resolve().parents[2] / "docs" / filename)
        path = next((candidate for candidate in candidates if candidate.is_file()), None)
        if path is None:
            QtWidgets.QMessageBox.warning(self, "SDRbridge", f"Help file unavailable: {filename}")
            return
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(self._t("help"))
        dialog.resize(880, 680)
        layout = QtWidgets.QVBoxLayout(dialog)
        browser = QtWidgets.QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setMarkdown(path.read_text(encoding="utf-8"))
        layout.addWidget(browser)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject); buttons.accepted.connect(dialog.accept)
        buttons.button(QtWidgets.QDialogButtonBox.Close).setText(self._t("close"))
        layout.addWidget(buttons)
        dialog.exec_()

    def _open_diagnostics(self) -> None:
        self.diagnostics_dialog.show(); self.diagnostics_dialog.raise_(); self.diagnostics_dialog.activateWindow()

    def _copy_diagnostics(self) -> None:
        QtWidgets.QApplication.clipboard().setText(self.diagnostics.toPlainText())

    def _export_diagnostics(self) -> None:
        default_folder = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        proposed = str(Path(default_folder or str(Path.home())) / f"SDRbridge-diagnostics-{timestamp}.zip")
        destination, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, self._t("save_diagnostics"), proposed, "ZIP (*.zip)"
        )
        if not destination:
            return
        try:
            raw = json.loads(self.diagnostics.toPlainText() or "{}")
            log_path = getattr(self.runtime, "log_path", None) if self.runtime is not None else None
            configuration = getattr(self.runtime, "config", {}) if self.runtime is not None else {}
            result = export_diagnostic_bundle(
                destination,
                app_version=__version__,
                diagnostics=raw,
                configuration=configuration,
                log_path=log_path,
            )
        except BaseException as exc:
            QtWidgets.QMessageBox.critical(self, "SDRbridge", self._t("diagnostics_export_failed").format(error=exc))
            return
        QtWidgets.QMessageBox.information(self, "SDRbridge", self._t("diagnostics_exported").format(path=result))

    def _retranslate_ui(self) -> None:
        self.tabs.setTabText(0, self._t("radio")); self.tabs.setTabText(1, self._t("clients"))
        self.tabs.setTabText(2, self._t("rf_profiles")); self.tabs.setTabText(3, self._t("captures"))
        self.source_metric_title.setText(self._t("source")); self.rate_metric_title.setText(self._t("measured_rate"))
        self.consumer_metric_title.setText(self._t("active_consumers")); self.udp_metric_title.setText(self._t("udp_throughput"))
        self.loss_metric_title.setText(self._t("top_losses")); self.cpu_metric_title.setText(self._t("process_cpu"))
        self.cpu_metric.setToolTip(self._t("process_cpu_tip")); self.cpu_label.setToolTip(self._t("process_cpu_tip"))
        self.start_button.setAccessibleName(self._t("start_stop_sdr")); self.compact_rx_button.setAccessibleName(self._t("start_stop_sdr"))
        self.compact_button.setToolTip(self._t("compact_view")); self.normal_view_button.setToolTip(self._t("normal_view"))
        self.settings_action.setText(self._t("settings")); self.help_action.setText(self._t("help")); self.diagnostics_action.setText(self._t("diagnostics")); self.about_action.setText(self._t("about"))
        self.frequency_title.setText(self._t("center_frequency")); self.receiver_group.setTitle(self._t("receiver"))
        self.source_sdr_label.setText(self._t("source_sdr")); self.device_refresh_button.setToolTip(self._t("refresh_sources"))
        self.device_refresh_button.setAccessibleName(self._t("refresh_sources")); self.iq_file_button.setToolTip(self._t("open_iq_file"))
        self.iq_file_button.setAccessibleName(self._t("open_iq_file")); self.iq_loop_check.setText(self._t("loop_iq_file"))
        picker_index = self.device_combo.findData(self.IQ_FILE_PICKER)
        if picker_index >= 0:
            self.device_combo.setItemText(picker_index, self._t("browse_iq_source"))
        self.rate_label.setText(self._t("sampling")); self.bandwidth_label.setText(self._t("bandwidth")); self.antenna_label.setText(self._t("antenna"))
        self.bandwidth_label.setToolTip(self._t("bandwidth_tip")); self.bandwidth_combo.setToolTip(self._t("bandwidth_tip"))
        if self._capabilities:
            self._refresh_bandwidth_combo(int(self.rate_edit.text()), int(self.bandwidth_edit.text()))
        self.if_gain_label.setText(self._gain_caption(self._primary_gain_names[0], 0)); self.rf_gain_label.setText(self._gain_caption(self._primary_gain_names[1], 1))
        self.if_gain_value.setText(self._gain_value_text(self._primary_gain_names[0], self.if_gain_slider.value()))
        self.rf_gain_value.setText(self._gain_value_text(self._primary_gain_names[1], self.rf_gain_slider.value()))
        extra_label_keys = {
            "bias_t_enabled": "bias_t", "rf_notch_enabled": "fm_notch", "rf_dab_notch_enabled": "dab_notch",
            "hdr_enabled": "hdr", "hdr_bw": "hdr_bandwidth", "if_type": "if_filter",
        }
        for name, label in self.extra_gain_labels.items():
            label.setText(self._t(extra_label_keys[name]) if name in extra_label_keys else name.replace("_", " ").title())
        self.auto_table_check.setText(self._t("auto_rf")); self.edit_table_button.setText(self._t("configure_rf"))
        self.rf_analysis_title.setText(self._t("rf_analysis")); self.smoothing_label.setText(self._t("smoothing"))
        self.smoothing_spin.setToolTip(self._t("smoothing_tip"))
        self.y_min_title.setText(self._t("display_min")); self.y_max_title.setText(self._t("display_max"))
        self.mode_spectrum.setText(self._t("spectrum")); self.mode_waterfall.setText(self._t("waterfall")); self.mode_split.setText(self._t("split"))
        for plot in (self.normal_plot, self.split_spectrum_plot):
            plot.setLabel("left", self._t("power_dbfs")); plot.setLabel("bottom", self._t("absolute_frequency"))
        for plot in (self.waterfall_plot, self.split_waterfall_plot):
            plot.setLabel("left", self._t("history")); plot.setLabel("bottom", self._t("absolute_frequency"))

        self.stream_consumers_title.setText(self._t("active_consumers")); self.stream_logical_title.setText(self._t("logical_iq_rate"))
        self.stream_network_title.setText(self._t("measured_network_rate")); self.stream_loss_title.setText(self._t("losses"))
        self.destinations_title.setText(self._t("destinations")); self.stream_refresh_button.setText(self._t("refresh"))
        self.consumer_table.setHorizontalHeaderLabels([self._t(key) for key in (
            "consumer_destination", "type", "protocol", "rate", "datagram", "queue", "packets_blocks", "losses", "status",
        )])
        self.profiles_table.setHorizontalHeaderLabels([self._t(key) for key in ("profile", "rate", "format", "protocol", "revision")])
        self.clients_table.setHorizontalHeaderLabels([self._t(key) for key in ("client", "blocks_read", "ring_drops", "last_sequence")])
        self.destinations_table.setHorizontalHeaderLabels([self._t(key) for key in (
            "destination", "transport", "output_rate", "datagram", "queue", "packets", "bytes", "queue_drops", "errors", "center_hz",
        )])
        self.destination_editor.setTitle(self._t("udp_editor"))
        self.destination_queue.setSuffix(self._t("blocks_suffix"))
        raw_index = self.destination_transport.findData("sdrpp_raw_cs16")
        if raw_index >= 0:
            self.destination_transport.setItemText(raw_index, self._t("sdrpp_raw"))
        for label, key in ((self.destination_endpoint_label, "endpoint"), (self.destination_transport_label, "transport"),
                           (self.destination_rate_label, "output_rate"), (self.destination_datagram_label, "datagram"),
                           (self.destination_queue_label, "queue")):
            label.setText(self._t(key))
        self.add_destination_button.setText(self._t("add_udp")); self.update_destination_button.setText(self._t("update_stream")); self.remove_destination_button.setText(self._t("remove"))
        self.udp_note_label.setText(self._t("udp_note")); self.native_network_label.setText(
            self._t("lan_udp_enabled") if self._lan_udp_enabled else self._t("lan_udp_disabled")
        )

        self.rf_automatic_title.setText(self._t("automatic_mode")); self.rf_rules_title.setText(self._t("rf_rules"))
        self.resume_rf_button.setText(self._t("resume_auto")); self.new_rf_rule_button.setText(self._t("new_rule"))
        self.edit_rf_rule_button.setText(self._t("edit")); self.remove_rf_rule_button.setText(self._t("remove"))
        self.rf_rules_table.setHorizontalHeaderLabels([self._t(key) for key in (
            "rule", "min_mhz", "max_mhz", "priority", "antenna", "agc", "if_rf", "bandwidth", "hysteresis", "state",
        )])
        self.rf_note_label.setText(self._t("rf_note"))

        self.capture_volume_title.setText(self._t("recorded_volume")); self.capture_rate_title.setText(self._t("measured_rate"))
        self.capture_source_title.setText(self._t("recorded_source")); self.capture_integrity_title.setText(self._t("integrity"))
        self.capture_group.setTitle(self._t("recording_config")); self.capture_format_label.setText(self._t("format"))
        self.capture_profile_label.setText(self._t("iq_profile")); self.capture_output_label.setText(self._t("output_file"))
        self.capture_format_combo.setItemText(self.capture_format_combo.findData(CaptureFormat.SDRPP_WAV.value), self._t("sdrpp_wav"))
        self.capture_format_combo.setItemText(self.capture_format_combo.findData(CaptureFormat.HDSDR_WAV.value), self._t("hdsdr_wav"))
        self.open_capture_folder_button.setText(self._t("open_folder")); self.capture_note_label.setText(self._t("capture_note"))

        self.diagnostics_dialog.setWindowTitle(self._t("diagnostics_title")); self.diagnostics_title.setText(self._t("system_diagnostics"))
        self.diagnostics_copy_button.setText(self._t("copy_json")); self.diagnostics_export_button.setText(self._t("export_diagnostics")); self.diagnostics_close_button.setText(self._t("close"))
        self.always_on_top.setText(self._t("top")); self.always_on_top.setToolTip(self._t("always_on_top"))
        self.refresh()

    def _build_topbar(self) -> QtWidgets.QWidget:
        bar = QtWidgets.QWidget(); layout = QtWidgets.QHBoxLayout(bar); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(8)
        self.start_button = QtWidgets.QToolButton()
        self.start_button.setAccessibleName(self._t("start_stop_sdr"))
        self.start_button.clicked.connect(self._toggle_rx)
        self.start_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.start_button.setProperty("success", False)
        self.start_button.setMinimumWidth(165); self.start_button.setMaximumHeight(58)
        self.source_metric, self.source_metric_title, self.state_label = self._metric_card("source")
        self.state_label.setAccessibleName("RX state")
        self.rate_metric, self.rate_metric_title, self.measured_rate_label = self._metric_card("measured_rate")
        self.consumer_metric, self.consumer_metric_title, self.consumer_count_label = self._metric_card("active_consumers")
        self.udp_metric, self.udp_metric_title, self.udp_rate_label = self._metric_card("udp_throughput")
        self.loss_metric, self.loss_metric_title, self.loss_label = self._metric_card("top_losses")
        self.cpu_metric, self.cpu_metric_title, self.cpu_label = self._metric_card("process_cpu")
        self.cpu_metric.setMinimumWidth(158)
        self.cpu_metric.setToolTip(self._t("process_cpu_tip")); self.cpu_label.setToolTip(self._t("process_cpu_tip"))
        self.frequency_effective = QtWidgets.QLabel("— Hz"); self.frequency_effective.hide()
        self.compact_button = QtWidgets.QToolButton()
        self.compact_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_TitleBarNormalButton))
        self.compact_button.setToolTip(self._t("compact_view"))
        self.compact_button.clicked.connect(self.toggle_compact)
        self.compact_button.setFixedSize(40, 40)
        self.settings_button = QtWidgets.QToolButton(); self.settings_button.setText("⚙"); self.settings_button.setPopupMode(QtWidgets.QToolButton.InstantPopup); self.settings_button.setFixedSize(40, 40)
        menu = QtWidgets.QMenu(self.settings_button)
        self.help_action = menu.addAction(self._t("help"), self._open_help)
        self.diagnostics_action = menu.addAction(self._t("diagnostics"), self._open_diagnostics)
        self.settings_action = menu.addAction(self._t("settings"), self._open_settings)
        self.about_action = menu.addAction(self._t("about"), self._open_about)
        self.settings_button.setMenu(menu)
        self.rec_top_label = QtWidgets.QLabel("● REC"); self.rec_top_label.setProperty("role", "danger"); self.rec_top_label.setVisible(False)
        self._play_icon = self.style().standardIcon(QtWidgets.QStyle.SP_MediaPlay)
        self._stop_icon = self.style().standardIcon(QtWidgets.QStyle.SP_MediaStop)
        self.start_button.setIcon(self._play_icon)
        layout.addWidget(self.start_button); layout.addWidget(self.source_metric); layout.addWidget(self.rate_metric)
        layout.addWidget(self.consumer_metric); layout.addWidget(self.udp_metric); layout.addWidget(self.loss_metric); layout.addWidget(self.cpu_metric)
        layout.addStretch(1); layout.addWidget(self.rec_top_label); layout.addWidget(self.compact_button); layout.addWidget(self.settings_button)
        return bar

    def _new_plot(self, compact=False) -> pg.PlotWidget:
        axis_items = {} if compact else {"bottom": AbsoluteFrequencyAxis(orientation="bottom")}
        plot = pg.PlotWidget(background="#071521", axisItems=axis_items)
        plot.setMouseEnabled(x=False, y=False)
        plot.showGrid(x=True, y=True, alpha=.2)
        plot.setYRange(-120, 5)
        plot.setLabel("left", self._t("power_dbfs"))
        plot.setLabel("bottom", self._t("absolute_frequency") if not compact else self._t("frequency_offset"))
        if compact:
            plot.hideAxis("left"); plot.hideAxis("bottom")
        else:
            plot.getAxis("left").setWidth(self.NORMAL_LEFT_AXIS_WIDTH)
        return plot

    def _new_waterfall_plot(self, compact: bool = False) -> tuple[pg.PlotWidget, pg.ImageItem]:
        axis_items = {} if compact else {"bottom": AbsoluteFrequencyAxis(orientation="bottom")}
        plot = pg.PlotWidget(background="#071521", axisItems=axis_items)
        plot.setMouseEnabled(x=False, y=False); plot.showGrid(x=True, y=True, alpha=.15)
        image = pg.ImageItem(axisOrder="row-major")
        colors = [
            (4, 18, 55), (7, 45, 125), (14, 85, 190), (22, 150, 230),
            (79, 220, 230), (245, 231, 91), (255, 150, 36), (255, 247, 222),
        ]
        image.setLookupTable(pg.ColorMap(np.linspace(0, 1, len(colors)), colors).getLookupTable(0.0, 1.0, 256))
        image.setLevels((-120, -20)); plot.addItem(image)
        if compact:
            plot.hideAxis("left"); plot.hideAxis("bottom")
        else:
            plot.setLabel("left", self._t("history"))
            plot.setLabel("bottom", self._t("absolute_frequency"))
            plot.getAxis("left").setWidth(self.NORMAL_LEFT_AXIS_WIDTH)
        return plot, image

    def _update_frequency_axes(self, center_frequency_hz: int) -> None:
        for plot in (
            self.normal_plot,
            self.waterfall_plot,
            self.split_spectrum_plot,
            self.split_waterfall_plot,
        ):
            axis = plot.getAxis("bottom")
            if isinstance(axis, AbsoluteFrequencyAxis):
                axis.set_center_frequency(center_frequency_hz)

    def _set_plot_mode(self, mode: str) -> None:
        if mode not in {"spectrum", "waterfall", "split"}:
            return
        self._plot_mode = mode
        index = {"spectrum": 0, "waterfall": 1, "split": 2}[mode]
        if hasattr(self, "plot_stack"):
            self.plot_stack.setCurrentIndex(index)
        if hasattr(self, "compact_plot_stack"):
            self.compact_plot_stack.setCurrentIndex(index)
        for button, name in ((self.mode_spectrum, "spectrum"), (self.mode_waterfall, "waterfall"), (self.mode_split, "split")):
            button.blockSignals(True); button.setChecked(name == mode); button.blockSignals(False)
        if self._settings is not None:
            self._settings.setValue("plot_mode", mode)

    def _build_normal(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget(); root = QtWidgets.QVBoxLayout(page); root.setContentsMargins(14, 10, 14, 8); root.setSpacing(8)
        root.addWidget(self._build_topbar())
        self.error_banner = QtWidgets.QLabel("")
        self.error_banner.setStyleSheet("background:#7a1f1f;color:white;padding:6px;")
        self.error_banner.setVisible(False); root.addWidget(self.error_banner)
        self.tabs = QtWidgets.QTabWidget(); root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._radio_tab(), self._t("radio"))
        self.tabs.addTab(self._streams_tab(), self._t("clients"))
        self.tabs.addTab(self._rf_tab(), self._t("rf_profiles"))
        self.tabs.addTab(self._capture_tab(), self._t("captures"))
        tab_bar = self.tabs.tabBar()
        tab_bar.setElideMode(QtCore.Qt.ElideNone)
        tab_bar.setExpanding(False)
        tab_bar.setUsesScrollButtons(False)
        self.status_bar = QtWidgets.QLabel("")
        self.status_bar.setProperty("role", "muted")
        root.addWidget(self.status_bar)
        self._build_diagnostics_dialog()
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

        frequency_row = QtWidgets.QHBoxLayout(); frequency_row.setContentsMargins(18, 12, 18, 12)
        self.frequency_title = QtWidgets.QLabel(self._t("center_frequency")); self.frequency_title.setProperty("role", "sectionTitle")
        frequency_row.addWidget(self.frequency_title)
        self.frequency_control = FrequencyControlWidget(tab)
        self.frequency_control.set_value_hz(cfg.center_frequency_hz)
        self.frequency_control.valueChanged.connect(self._frequency_changed)
        self.frequency_edit.editingFinished.connect(self._legacy_frequency_changed)
        frequency_row.addWidget(self.frequency_control, 1)
        self.center_frequency_label = QtWidgets.QLabel(); self.center_frequency_label.hide()  # compatibility alias
        self.frequency_card = self._card(frequency_row)

        self.receiver_group = QtWidgets.QGroupBox(self._t("receiver"))
        source_layout = QtWidgets.QVBoxLayout(self.receiver_group)

        source_top = QtWidgets.QGridLayout()
        self.device_combo = QtWidgets.QComboBox()
        self.device_combo.currentIndexChanged.connect(self._select_device)
        self.device_refresh_button = QtWidgets.QToolButton()
        self.device_refresh_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_BrowserReload))
        self.device_refresh_button.setToolTip(self._t("refresh_sources"))
        self.device_refresh_button.setAccessibleName(self._t("refresh_sources"))
        self.device_refresh_button.clicked.connect(self._refresh_devices)
        self.iq_file_button = QtWidgets.QToolButton()
        self.iq_file_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogOpenButton))
        self.iq_file_button.setToolTip(self._t("open_iq_file"))
        self.iq_file_button.setAccessibleName(self._t("open_iq_file"))
        self.iq_file_button.clicked.connect(self._choose_iq_file)
        self.iq_file_button.setEnabled(self.runtime is not None and hasattr(self.runtime, "select_iq_file"))
        self.source_sdr_label = QtWidgets.QLabel(self._t("source_sdr"))
        source_top.addWidget(self.source_sdr_label, 0, 0)
        source_top.addWidget(self.device_combo, 0, 1)
        source_top.addWidget(self.device_refresh_button, 0, 2)
        source_top.addWidget(self.iq_file_button, 0, 3)
        self.connection_label = QtWidgets.QLabel(""); self.connection_label.hide()  # compatibility alias
        self.iq_loop_check = QtWidgets.QCheckBox(self._t("loop_iq_file"))
        self.iq_loop_check.toggled.connect(self._iq_loop_changed)
        self.iq_loop_check.setVisible(False)
        source_top.addWidget(self.iq_loop_check, 2, 1, 1, 3)
        source_layout.addLayout(source_top)

        controls = QtWidgets.QGridLayout()
        self.rate_combo = QtWidgets.QComboBox(); self.rate_combo.currentIndexChanged.connect(self._rate_changed)
        self.bandwidth_combo = QtWidgets.QComboBox(); self.bandwidth_combo.currentIndexChanged.connect(self._bandwidth_changed)
        self.antenna_combo = QtWidgets.QComboBox(); self.antenna_combo.currentIndexChanged.connect(lambda _index: self._manual_rf_control_changed())
        self.antenna_label = QtWidgets.QLabel(self._t("antenna"))
        self.rate_label = QtWidgets.QLabel(self._t("sampling")); self.bandwidth_label = QtWidgets.QLabel(self._t("bandwidth"))
        controls.addWidget(self.rate_label, 0, 0); controls.addWidget(self.rate_combo, 0, 1)
        controls.addWidget(self.bandwidth_label, 0, 2); controls.addWidget(self.bandwidth_combo, 0, 3)
        controls.addWidget(self.antenna_label, 0, 4); controls.addWidget(self.antenna_combo, 0, 5)
        self.if_gain_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.if_gain_slider.setRange(0, 100); self.if_gain_slider.setInvertedAppearance(True); self.if_gain_slider.setValue(cfg.gain_reduction_db)
        self.rf_gain_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.rf_gain_slider.setRange(0, 27); self.rf_gain_slider.setInvertedAppearance(True); self.rf_gain_slider.setValue(int(cfg.gains.get("lna_state", 0)))
        self.gain_slider = self.if_gain_slider  # historical attribute
        self.if_gain_slider.valueChanged.connect(lambda value: self._primary_gain_changed(0, value))
        self.rf_gain_slider.valueChanged.connect(lambda value: self._primary_gain_changed(1, value))
        self.if_gain_label = QtWidgets.QLabel(self._t("if_gain")); self.rf_gain_label = QtWidgets.QLabel(self._t("rf_gain"))
        self.if_gain_value = QtWidgets.QLabel("—"); self.if_gain_value.setProperty("role", "muted")
        self.rf_gain_value = QtWidgets.QLabel("—"); self.rf_gain_value.setProperty("role", "muted")
        if_holder = QtWidgets.QWidget(); if_row = QtWidgets.QHBoxLayout(if_holder); if_row.setContentsMargins(0, 0, 0, 0); if_row.addWidget(self.if_gain_slider, 1); if_row.addWidget(self.if_gain_value)
        rf_holder = QtWidgets.QWidget(); rf_row = QtWidgets.QHBoxLayout(rf_holder); rf_row.setContentsMargins(0, 0, 0, 0); rf_row.addWidget(self.rf_gain_slider, 1); rf_row.addWidget(self.rf_gain_value)
        controls.addWidget(self.if_gain_label, 1, 0); controls.addWidget(if_holder, 1, 1)
        controls.addWidget(self.rf_gain_label, 1, 2); controls.addWidget(rf_holder, 1, 3)
        self.agc_check = QtWidgets.QCheckBox("AGC"); self.agc_check.setChecked(cfg.agc_enabled); self.agc_check.stateChanged.connect(lambda _state: self._manual_rf_control_changed())
        self.auto_table_check = QtWidgets.QCheckBox(self._t("auto_rf")); self.auto_table_check.setChecked(not self.rf_profiles.suspended); self.auto_table_check.toggled.connect(self._auto_table_toggled)
        self.edit_table_button = QtWidgets.QPushButton(self._t("configure_rf")); self.edit_table_button.clicked.connect(lambda: self.tabs.setCurrentIndex(2))
        controls.addWidget(self.auto_table_check, 1, 4); controls.addWidget(self.edit_table_button, 1, 5)
        source_layout.addLayout(controls)
        self.dynamic_container = QtWidgets.QWidget(self.receiver_group)
        self.extra_gains_form = QtWidgets.QHBoxLayout(self.dynamic_container)
        self.extra_gain_controls = {}
        self.extra_gain_labels: dict[str, QtWidgets.QLabel | QtWidgets.QCheckBox] = {}
        options_row = QtWidgets.QHBoxLayout()
        options_row.addWidget(self.agc_check)
        options_row.addWidget(self.dynamic_container, 1)
        source_layout.addLayout(options_row)
        layout.addWidget(self.receiver_group)
        layout.addWidget(self.frequency_card)

        plot_card = QtWidgets.QFrame(); self.plot_card = plot_card; plot_card.setProperty("card", True); plot_layout = QtWidgets.QVBoxLayout(plot_card); plot_layout.setContentsMargins(12, 8, 12, 10)
        fft_form = QtWidgets.QHBoxLayout()
        self.rf_analysis_title = QtWidgets.QLabel(self._t("rf_analysis")); self.rf_analysis_title.setProperty("role", "sectionTitle"); fft_form.addWidget(self.rf_analysis_title)
        self.mode_spectrum = QtWidgets.QToolButton(); self.mode_spectrum.setText(self._t("spectrum")); self.mode_spectrum.setCheckable(True); self.mode_spectrum.clicked.connect(lambda: self._set_plot_mode("spectrum"))
        self.mode_waterfall = QtWidgets.QToolButton(); self.mode_waterfall.setText(self._t("waterfall")); self.mode_waterfall.setCheckable(True); self.mode_waterfall.clicked.connect(lambda: self._set_plot_mode("waterfall"))
        self.mode_split = QtWidgets.QToolButton(); self.mode_split.setText(self._t("split")); self.mode_split.setCheckable(True); self.mode_split.clicked.connect(lambda: self._set_plot_mode("split"))
        fft_form.addWidget(self.mode_spectrum); fft_form.addWidget(self.mode_waterfall); fft_form.addWidget(self.mode_split)
        self.fft_size_combo = QtWidgets.QComboBox()
        self.fft_size_values = tuple(2 ** exponent for exponent in range(8, 18))
        for value in self.fft_size_values:
            self.fft_size_combo.addItem(f"{value:,}".replace(",", " "), value)
        self.fft_size_combo.setCurrentIndex(self.fft_size_values.index(4096))
        self.fft_size_combo.currentIndexChanged.connect(lambda index: setattr(self.spectrum, "fft_size", int(self.fft_size_combo.itemData(index))) if hasattr(self, "spectrum") else None)
        self.fft_size_spin = self.fft_size_combo  # compatibility attribute
        self.smoothing_spin = QtWidgets.QDoubleSpinBox(); self.smoothing_spin.setRange(0, .95); self.smoothing_spin.setSingleStep(.05); self.smoothing_spin.setValue(0); self.smoothing_spin.setToolTip(self._t("smoothing_tip"))
        self.smoothing_spin.valueChanged.connect(lambda value: setattr(self.spectrum, "smoothing", float(value)) if hasattr(self, "spectrum") else None)
        self.fft_label = QtWidgets.QLabel("FFT")
        self.smoothing_label = QtWidgets.QLabel(self._t("smoothing"))
        fft_form.addStretch(1); fft_form.addWidget(self.fft_label); fft_form.addWidget(self.fft_size_combo); fft_form.addWidget(self.smoothing_label); fft_form.addWidget(self.smoothing_spin)
        plot_layout.addLayout(fft_form)

        self.plot_stack = QtWidgets.QStackedWidget()
        self.normal_plot = self._new_plot(); self.normal_curve = self.normal_plot.plot(pen=pg.mkPen("#37D7FF", width=1.3), fillLevel=-120, brush=pg.mkBrush(15, 130, 190, 80)); self.plot_stack.addWidget(self.normal_plot)
        self.waterfall_plot, self.waterfall_image = self._new_waterfall_plot(); self.plot_stack.addWidget(self.waterfall_plot)
        split = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.split_spectrum_plot = self._new_plot(); self.split_spectrum_curve = self.split_spectrum_plot.plot(pen=pg.mkPen("#37D7FF", width=1.2), fillLevel=-120, brush=pg.mkBrush(15, 130, 190, 60))
        self.split_waterfall_plot, self.split_waterfall_image = self._new_waterfall_plot()
        split.addWidget(self.split_spectrum_plot); split.addWidget(self.split_waterfall_plot); split.setSizes([130, 220]); self.plot_stack.addWidget(split)
        self._update_frequency_axes(cfg.center_frequency_hz)

        display_row = QtWidgets.QHBoxLayout(); display_row.setSpacing(10); display_row.addWidget(self.plot_stack, 1)
        self.scale_panel = QtWidgets.QFrame(); self.scale_panel.setProperty("scalePanel", True); self.scale_panel.setFixedWidth(48)
        scale_layout = QtWidgets.QVBoxLayout(self.scale_panel); scale_layout.setContentsMargins(6, 5, 6, 5); scale_layout.setSpacing(2)

        self.y_min_slider = QtWidgets.QSlider(QtCore.Qt.Vertical); self.y_min_slider.setRange(-160, -20); self.y_min_slider.setSingleStep(5); self.y_min_slider.setPageStep(10); self.y_min_slider.setValue(-120)
        self.y_max_slider = QtWidgets.QSlider(QtCore.Qt.Vertical); self.y_max_slider.setRange(-80, 20); self.y_max_slider.setSingleStep(5); self.y_max_slider.setPageStep(10); self.y_max_slider.setValue(5)
        self.y_min_title = QtWidgets.QLabel(self._t("display_min")); self.y_min_title.setAlignment(QtCore.Qt.AlignCenter)
        self.y_max_title = QtWidgets.QLabel(self._t("display_max")); self.y_max_title.setAlignment(QtCore.Qt.AlignCenter)
        scale_layout.addWidget(self.y_max_title)
        scale_layout.addWidget(self.y_max_slider, 1)
        scale_layout.addWidget(self.y_min_title)
        scale_layout.addWidget(self.y_min_slider, 1)
        display_row.addWidget(self.scale_panel)
        plot_layout.addLayout(display_row, 1)

        self.y_min_slider.valueChanged.connect(lambda _value: self._apply_y_range("min"))
        self.y_max_slider.valueChanged.connect(lambda _value: self._apply_y_range("max"))
        # Compatibility handles for automation written against v0.3.  They
        # remain hidden; the two vertical sliders above are the front-panel controls.
        self.y_min_spin = QtWidgets.QDoubleSpinBox(self.receiver_group); self.y_min_spin.setRange(-160, -20); self.y_min_spin.setValue(-120); self.y_min_spin.hide()
        self.y_max_spin = QtWidgets.QDoubleSpinBox(self.receiver_group); self.y_max_spin.setRange(-40, 20); self.y_max_spin.setValue(5); self.y_max_spin.hide()
        self.y_min_spin.valueChanged.connect(lambda value: self.y_min_slider.setValue(int(value)))
        self.y_max_spin.valueChanged.connect(lambda value: self.y_max_slider.setValue(int(value)))
        self._apply_y_range()
        layout.addWidget(plot_card, 1)
        self._set_plot_mode(self._plot_mode)
        return tab

    def _apply_y_range(self, changed: str | None = None) -> None:
        low, high = self.y_min_slider.value(), self.y_max_slider.value()
        if high <= low:
            if changed == "min":
                high = min(self.y_max_slider.maximum(), low + 5)
                self.y_max_slider.blockSignals(True); self.y_max_slider.setValue(high); self.y_max_slider.blockSignals(False)
            else:
                low = max(self.y_min_slider.minimum(), high - 5)
                self.y_min_slider.blockSignals(True); self.y_min_slider.setValue(low); self.y_min_slider.blockSignals(False)
        self.normal_plot.setYRange(low, high, padding=0)
        if hasattr(self, "split_spectrum_plot"):
            self.split_spectrum_plot.setYRange(low, high, padding=0)
        if hasattr(self, "compact_plot"):
            self.compact_plot.setYRange(low, high, padding=0)
        if hasattr(self, "compact_split_plot"):
            self.compact_split_plot.setYRange(low, high, padding=0)
        for name in ("normal_curve", "split_spectrum_curve", "compact_curve", "compact_split_curve"):
            curve = getattr(self, name, None)
            if curve is not None:
                curve.setFillLevel(low)
        for name in ("waterfall_image", "split_waterfall_image", "compact_waterfall_image", "compact_split_waterfall_image"):
            image = getattr(self, name, None)
            if image is not None:
                image.setLevels((low, high))

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
            self._apply_rf_profile(int(value))
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
            self._bandwidth_auto = bool(self.bandwidth_combo.itemData(index, self.BANDWIDTH_AUTO_ROLE))
            if self._settings is not None:
                self._settings.setValue("bandwidth_auto", 1 if self._bandwidth_auto else 0)
                self._settings.sync()
            self.bandwidth_edit.setText(str(int(value)))
            self._manual_rf_control_changed()

    def _set_dynamic_value(self, name: str, value: int) -> None:
        control = self.extra_gain_controls.get(name)
        if control is not None and control.value() != int(value):
            control.blockSignals(True); control.setValue(int(value)); control.blockSignals(False)
        self._schedule_live_apply()

    def _manual_rf_control_changed(self) -> None:
        if self._applying_rf_profile:
            self._schedule_live_apply()
            return
        if self.auto_table_check.isChecked():
            self.auto_table_check.setChecked(False)
        self._schedule_live_apply()

    def _gain_caption(self, name: str | None, slot: int) -> str:
        if not name:
            return self._t("if_gain") if slot == 0 else self._t("rf_gain")
        upper = name.upper()
        if upper == "IFGR":
            return self._t("if_gain_reduction")
        if upper == "RFGR":
            return self._t("rf_gain_reduction")
        return name.replace("_", " ")

    def _gain_value_text(self, name: str | None, value: float) -> str:
        if not name:
            return "—"
        if name.upper() == "IFGR":
            return self._t("reduction_value").format(value=value)
        if name.upper() == "RFGR":
            return self._t("lna_state_value").format(value=value)
        return f"{value:g} dB"

    def _primary_gain_changed(self, slot: int, value: int) -> None:
        name = self._primary_gain_names[slot]
        if name and not self._applying_rf_profile and self.auto_table_check.isChecked():
            self.auto_table_check.setChecked(False)
        if slot == 0:
            self.gain_edit.setText(str(int(value)))
            self.if_gain_value.setText(self._gain_value_text(name, value))
        else:
            self.rf_gain_value.setText(self._gain_value_text(name, value))
        self._schedule_live_apply()

    def _configure_primary_gains(self, capabilities: dict) -> set[str]:
        ranges = capabilities.get("gain_ranges", {})
        names = list(ranges)
        upper_map = {name.upper(): name for name in names}
        first = upper_map.get("IFGR") or upper_map.get("GAIN_REDUCTION_DB")
        second = upper_map.get("RFGR") or upper_map.get("LNA_STATE")
        if first is None and names:
            first = names[0]
        if second is None:
            second = next((name for name in names if name != first), None)
        self._primary_gain_names = [first, second]
        used = {name for name in self._primary_gain_names if name}
        values = capabilities.get("gain_values", {})
        for slot, (name, slider, label, value_label) in enumerate((
            (first, self.if_gain_slider, self.if_gain_label, self.if_gain_value),
            (second, self.rf_gain_slider, self.rf_gain_label, self.rf_gain_value),
        )):
            label.setText(self._gain_caption(name, slot))
            available = name is not None and name in ranges
            label.setVisible(available); slider.parentWidget().setVisible(available)
            if not available:
                continue
            low, high = map(float, ranges[name])
            slider.blockSignals(True); slider.setRange(round(low), round(high))
            fallback = self.bridge.config.gains.get(name, low)
            slider.setValue(round(float(values.get(name, fallback)))); slider.blockSignals(False)
            # SDRplay IFGR/RFGR are reductions: right means more real gain.
            slider.setInvertedAppearance(name.upper() in {"IFGR", "RFGR", "GAIN_REDUCTION_DB", "LNA_STATE"})
            value_label.setText(self._gain_value_text(name, slider.value()))
        return used

    def _set_hardware_controls_enabled(self, enabled: bool) -> None:
        self.frequency_control.set_editable(enabled)
        self.rate_combo.setEnabled(enabled and bool(
            self._capabilities.get("sample_rates_sps") or self._capabilities.get("sample_rate_ranges_sps")
        ))
        self.bandwidth_combo.setEnabled(enabled and bool(
            self._capabilities.get("bandwidths_hz") or self._capabilities.get("bandwidth_ranges_hz")
        ))
        self.antenna_combo.setEnabled(enabled and self.antenna_combo.count() > 0)
        self.if_gain_slider.setEnabled(enabled and self._primary_gain_names[0] is not None)
        self.rf_gain_slider.setEnabled(enabled and self._primary_gain_names[1] is not None)
        self.agc_check.setEnabled(enabled and bool(self._capabilities.get("agc_available", False)))
        self.auto_table_check.setEnabled(enabled)
        self.edit_table_button.setEnabled(enabled)
        self.dynamic_container.setEnabled(enabled)

    def _auto_table_toggled(self, enabled: bool) -> None:
        if enabled:
            self.rf_profiles.resume()
        else:
            self.rf_profiles.suspend_manual()
            self._active_rf_rule_id = None
        if enabled:
            self._apply_rf_profile(self.frequency_control.value_hz())
        self._save_rf_profiles()
        if hasattr(self, "rf_auto_status"):
            self._refresh_rf_rules()
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
            if self.runtime is not None and hasattr(self.runtime, "available_sources"):
                devices = self.runtime.available_sources()
            else:
                devices = self.bridge.enumerate_devices()
            current = self.bridge.device_id
            # A discovery-only configuration intentionally stores no device
            # identifier. The combo nevertheless displayed its first item
            # while the bridge still had no effective source selected, which
            # left all capability controls blank and made Play ineffective.
            # Claim the first deterministically sorted RX device while stopped.
            if current is None and devices:
                first_device_id = devices[0].get("device_id")
                if first_device_id:
                    if self.runtime is not None and hasattr(self.runtime, "select_source_device"):
                        self.runtime.select_source_device(str(first_device_id))
                    else:
                        self.bridge.select_device(str(first_device_id))
                    current = self.bridge.device_id
            self.device_combo.blockSignals(True)
            self.device_combo.clear()
            for device in devices:
                label = device.get("model") or device.get("label") or device.get("device_id")
                serial = device.get("serial")
                suffix = f" — S/N {serial}" if serial and str(serial) not in str(label) else ""
                self.device_combo.addItem(f"{device.get('backend', '')}: {label}{suffix}", device.get("device_id"))
            if self.runtime is not None and hasattr(self.runtime, "select_iq_file"):
                self.device_combo.insertSeparator(self.device_combo.count())
                self.device_combo.addItem(self._t("browse_iq_source"), self.IQ_FILE_PICKER)
            if current:
                index = self.device_combo.findData(current)
                if index >= 0:
                    self.device_combo.setCurrentIndex(index)
                capabilities = self.bridge.capabilities(current)
                self._capabilities = capabilities
                self._capability_refresh_attempts = 3
                frequency_ranges = capabilities.get("frequency_ranges_hz", ())
                if frequency_ranges:
                    self.frequency_control.set_range_hz(
                        min(int(item[0]) for item in frequency_ranges),
                        max(int(item[1]) for item in frequency_ranges),
                    )
                else:
                    self.frequency_control.set_range_hz(1_000, MAX_CENTER_FREQUENCY_HZ)
                used_primary_gains = self._configure_primary_gains(capabilities)
                self.agc_check.setEnabled(bool(capabilities.get("agc_available", False)))
                rate_values = capabilities.get("sample_rates_sps", ()) or (self.bridge.config.sample_rate_sps,)
                self._fill_capability_combo(self.rate_combo, rate_values, self.bridge.config.sample_rate_sps, "MHz")
                self._refresh_bandwidth_combo(self.bridge.config.sample_rate_sps, self.bridge.config.bandwidth_hz)
                self.antenna_combo.blockSignals(True)
                self.antenna_combo.clear()
                for antenna in capabilities.get("antennas", ()):
                    self.antenna_combo.addItem(str(antenna), str(antenna))
                if self.antenna_combo.count() == 0 and self.bridge.config.antenna:
                    self.antenna_combo.addItem(str(self.bridge.config.antenna), str(self.bridge.config.antenna))
                antenna_index = self.antenna_combo.findData(self.bridge.config.antenna)
                if antenna_index >= 0:
                    self.antenna_combo.setCurrentIndex(antenna_index)
                self.antenna_combo.blockSignals(False)
                while self.extra_gains_form.count():
                    item = self.extra_gains_form.takeAt(0)
                    if item.widget() is not None:
                        item.widget().deleteLater()
                self.extra_gain_controls.clear()
                self.extra_gain_labels.clear()
                label_keys = {
                    "bias_t_enabled": "bias_t", "rf_notch_enabled": "fm_notch",
                    "rf_dab_notch_enabled": "dab_notch", "hdr_enabled": "hdr",
                    "hdr_bw": "hdr_bandwidth", "if_type": "if_filter",
                }
                for name, bounds in capabilities.get("gain_ranges", {}).items():
                    if name in used_primary_gains:
                        continue
                    low, high = map(float, bounds)
                    value = float(capabilities.get("gain_values", {}).get(name, self.bridge.config.gains.get(name, low)))
                    shown_label = self._t(label_keys[name]) if name in label_keys else name.replace("_", " ").title()
                    if name.endswith("_enabled"):
                        control = QtWidgets.QCheckBox(shown_label)
                        control.setChecked(bool(value)); control.stateChanged.connect(lambda _state: self._manual_rf_control_changed())
                        self.extra_gain_labels[name] = control
                    elif name in {"hdr_bw", "if_type"}:
                        control = QtWidgets.QComboBox()
                        options = (("0.2 MHz", 0), ("0.5 MHz", 1), ("1.2 MHz", 2), ("1.7 MHz", 3)) if name == "hdr_bw" else (("0 kHz", 0), ("450 kHz", 1), ("1,620 kHz", 2), ("2,048 kHz", 3))
                        for label, option in options:
                            control.addItem(label, option)
                        control.setCurrentIndex(max(0, min(3, round(value)))); control.currentIndexChanged.connect(lambda _index: self._manual_rf_control_changed())
                    else:
                        control = QtWidgets.QSlider(QtCore.Qt.Horizontal); control.setRange(round(low), round(high)); control.setValue(round(value)); control.valueChanged.connect(lambda _value: self._manual_rf_control_changed())
                    if name.endswith("_enabled"):
                        self.extra_gains_form.addWidget(control)
                    else:
                        holder = QtWidgets.QWidget(self.dynamic_container)
                        row = QtWidgets.QHBoxLayout(holder); row.setContentsMargins(3, 0, 3, 0)
                        extra_label = QtWidgets.QLabel(shown_label)
                        row.addWidget(extra_label)
                        row.addWidget(control)
                        self.extra_gains_form.addWidget(holder)
                        self.extra_gain_labels[name] = extra_label
                    self.extra_gain_controls[name] = control
                self.dynamic_container.setVisible(bool(self.extra_gain_controls))
            is_file = str(current or "").startswith("file:")
            self.iq_loop_check.blockSignals(True)
            self.iq_loop_check.setChecked(bool(getattr(self.bridge.source, "loop", False)))
            self.iq_loop_check.blockSignals(False)
            self.iq_loop_check.setVisible(is_file)
            self._set_hardware_controls_enabled(not is_file)
            self.device_combo.blockSignals(False)
            hardware_error_prefixes = tuple(
                translations["hardware_controls_unavailable"].split("{error}", 1)[0]
                for translations in TEXT.values()
            )
            if self.error_banner.text().startswith(hardware_error_prefixes):
                self._show_error("")
        except Exception as exc:
            # Keep the current source visible and retry from refresh(). An
            # early capability query can race the first SDRplay device claim;
            # clearing the selector here hid a perfectly operational source.
            self._capabilities = {}
            logger.exception(
                "hardware capability refresh failed",
                extra={"code": "GUI_HARDWARE_CAPABILITY_REFRESH_FAILED"},
            )
            if self.device_combo.count() == 0:
                self.device_combo.addItem(self._t("discovery_unavailable").format(error=exc))
            self._show_error(self._t("hardware_controls_unavailable").format(error=exc))

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
        """Expose hardware filters and select the closest one in Auto mode."""
        all_bandwidths = tuple(int(value) for value in self._capabilities.get("bandwidths_hz", ()))
        has_hardware_bandwidth = bool(
            all_bandwidths or self._capabilities.get("bandwidth_ranges_hz", ())
        )
        if not has_hardware_bandwidth:
            effective = int(current_bandwidth_hz or sample_rate_sps)
            self.bandwidth_combo.blockSignals(True)
            self.bandwidth_combo.clear()
            self.bandwidth_combo.addItem(self._t("bandwidth_unavailable"), effective)
            self.bandwidth_combo.setCurrentIndex(0)
            self.bandwidth_combo.blockSignals(False)
            self.bandwidth_edit.setText(str(effective))
            return
        all_bandwidths = tuple(sorted(set(all_bandwidths)))
        current = int(current_bandwidth_hz if current_bandwidth_hz is not None else self.bandwidth_edit.text())
        if not all_bandwidths:
            return
        automatic = min(all_bandwidths, key=lambda value: (abs(value - int(sample_rate_sps)), value))
        manual = min(all_bandwidths, key=lambda value: (abs(value - current), value))
        self.bandwidth_combo.blockSignals(True)
        self.bandwidth_combo.clear()
        self.bandwidth_combo.addItem(self._t("bandwidth_auto").format(value=automatic / 1e6), automatic)
        self.bandwidth_combo.setItemData(0, True, self.BANDWIDTH_AUTO_ROLE)
        for value in all_bandwidths:
            self.bandwidth_combo.addItem(f"{value / 1e6:.3f} MHz", value)
            self.bandwidth_combo.setItemData(self.bandwidth_combo.count() - 1, False, self.BANDWIDTH_AUTO_ROLE)
        if self._bandwidth_auto:
            selected_index = 0
            effective = automatic
        else:
            selected_index = 1 + all_bandwidths.index(manual)
            effective = manual
        self.bandwidth_combo.setCurrentIndex(selected_index)
        self.bandwidth_combo.blockSignals(False)
        self.bandwidth_edit.setText(str(effective))

    def _select_device(self, index: int) -> None:
        device_id = self.device_combo.itemData(index)
        if not device_id:
            return
        if device_id == self.IQ_FILE_PICKER:
            self._choose_iq_file()
            return
        if device_id == self.bridge.device_id:
            return
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            self._capabilities = {}
            self._capability_refresh_attempts = 0
            if self.runtime is not None and hasattr(self.runtime, "select_source_device"):
                self.runtime.select_source_device(str(device_id))
            else:
                self.bridge.select_device(str(device_id))
            if self.bridge.device_id != str(device_id):
                raise RuntimeError("the selected source did not become active")
            self.spectrum.resync_after_reconfigure()
            self._show_error("")
            self._refresh_devices()
        except Exception as exc:
            self._show_error(self._t("device_rejected").format(error=exc))
            # Restore the selector to the effective source.  Leaving the
            # rejected SDR highlighted made the operator believe the file had
            # been replaced even though the bridge had correctly rolled back.
            self._refresh_devices()
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self.refresh()

    def _choose_iq_file(self) -> None:
        if self.runtime is None or not hasattr(self.runtime, "select_iq_file"):
            self._show_error(self._t("iq_selection_unavailable"))
            return
        current_path = getattr(self.runtime, "iq_file_path", None)
        start_directory = str(Path(current_path).parent) if current_path else str(Path.home())
        path, _selected_filter = QtWidgets.QFileDialog.getOpenFileName(
            self,
            self._t("select_iq_recording"),
            start_directory,
            self._t("format_filter"),
        )
        if not path:
            self._refresh_devices()
            return
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            self.runtime.select_iq_file(path, loop=self.iq_loop_check.isChecked())
            self.spectrum.resync_after_reconfigure()
            self._show_error("")
        except Exception as exc:
            self._show_error(self._t("iq_file_rejected").format(error=exc))
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
            self._refresh_devices()
            self.refresh()

    def _iq_loop_changed(self, enabled: bool) -> None:
        if self.runtime is not None and hasattr(self.runtime, "set_iq_file_loop"):
            self.runtime.set_iq_file_loop(bool(enabled))

    def _streams_tab(self) -> QtWidgets.QWidget:
        tab = QtWidgets.QWidget(); layout = QtWidgets.QVBoxLayout(tab); layout.setSpacing(10)
        summary = QtWidgets.QHBoxLayout()
        self.stream_consumers_card, self.stream_consumers_title, self.stream_consumers_value = self._metric_card("active_consumers")
        self.stream_logical_card, self.stream_logical_title, self.stream_logical_value = self._metric_card("udp_throughput")
        self.stream_logical_title.setText(self._t("logical_iq_rate"))
        self.stream_network_card, self.stream_network_title, self.stream_network_value = self._metric_card("udp_throughput")
        self.stream_network_title.setText(self._t("measured_network_rate"))
        self.stream_loss_card, self.stream_loss_title, self.stream_loss_value = self._metric_card("losses")
        for card in (self.stream_consumers_card, self.stream_logical_card, self.stream_network_card, self.stream_loss_card):
            summary.addWidget(card)
        summary.addStretch(1); layout.addLayout(summary)

        title_row = QtWidgets.QHBoxLayout()
        self.destinations_title = QtWidgets.QLabel(self._t("destinations")); self.destinations_title.setProperty("role", "sectionTitle")
        title_row.addWidget(self.destinations_title); title_row.addStretch(1)
        self.stream_refresh_button = QtWidgets.QPushButton(self._t("refresh")); self.stream_refresh_button.clicked.connect(self.refresh); title_row.addWidget(self.stream_refresh_button)
        layout.addLayout(title_row)
        self.consumer_table = QtWidgets.QTableWidget(0, 9)
        self.consumer_table.setHorizontalHeaderLabels([self._t(key) for key in (
            "consumer_destination", "type", "protocol", "rate", "datagram", "queue", "packets_blocks", "losses", "status",
        )])
        self.consumer_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.consumer_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.consumer_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.consumer_table.itemSelectionChanged.connect(self._consumer_selected)
        layout.addWidget(self.consumer_table, 1)

        # Kept as hidden compatibility models for tests and existing operator
        # automation.  The visible v0.7 table above unifies these three views.
        self.profiles_table = QtWidgets.QTableWidget(0, 5)
        self.profiles_table.setHorizontalHeaderLabels([self._t(key) for key in ("profile", "rate", "format", "protocol", "revision")])
        profiles = self.bridge.profiles.items(); self.profiles_table.setRowCount(len(profiles))
        for row, profile in enumerate(profiles):
            for column, value in enumerate((profile.name or profile.profile_id, profile.output_rate_sps, profile.sample_format.value, profile.protocol, profile.profile_revision)):
                self.profiles_table.setItem(row, column, QtWidgets.QTableWidgetItem(str(value)))
        self.profiles_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.profiles_table.hide()
        self.clients_table = QtWidgets.QTableWidget(0, 4)
        self.clients_table.setHorizontalHeaderLabels([self._t(key) for key in ("client", "blocks_read", "ring_drops", "last_sequence")])
        self.clients_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.clients_table.hide()
        self.destinations_table = QtWidgets.QTableWidget(0, 10)
        self.destinations_table.setHorizontalHeaderLabels([self._t(key) for key in (
            "destination", "transport", "output_rate", "datagram", "queue", "packets", "bytes", "queue_drops", "errors", "center_hz",
        )])
        self.destinations_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.destinations_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.destinations_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.destinations_table.itemSelectionChanged.connect(self._destination_selected)
        self.destinations_table.hide()
        self.destination_editor = QtWidgets.QGroupBox(self._t("udp_editor")); destination_controls = QtWidgets.QGridLayout(self.destination_editor)
        self.destination_edit = QtWidgets.QLineEdit("127.0.0.1:7356")
        self.destination_edit.setPlaceholderText("HOST:PORT")
        self.destination_edit.editingFinished.connect(self._destination_endpoint_changed)
        self.destination_transport = QtWidgets.QComboBox()
        self.destination_transport.addItem(self._t("sdrpp_raw"), "sdrpp_raw_cs16")
        self.destination_transport.addItem("SDBU v2", "sdbu_v2")
        self.destination_transport.addItem("QMAP / Linrad 96 kS/s", "qmap_linrad")
        self.destination_transport.currentIndexChanged.connect(self._destination_transport_changed)
        self.destination_rate = QtWidgets.QSpinBox()
        self.destination_rate.setRange(1, 20_000_000)
        self.destination_rate.setSingleStep(1_000)
        self.destination_rate.setValue(self.bridge.config.sample_rate_sps)
        self.destination_rate.setSuffix(" S/s")
        self.destination_rate.setGroupSeparatorShown(True)
        self.destination_datagram = QtWidgets.QSpinBox()
        self.destination_datagram.setRange(256, 65_507)
        self.destination_datagram.setValue(8192)
        self.destination_datagram.setSuffix(" B")
        self.destination_queue = QtWidgets.QSpinBox()
        self.destination_queue.setRange(4, 4096)
        self.destination_queue.setValue(32)
        self.destination_queue.setSuffix(self._t("blocks_suffix"))
        self.add_destination_button = QtWidgets.QPushButton(self._t("add_udp"))
        self.add_destination_button.clicked.connect(self._add_udp_destination)
        self.update_destination_button = QtWidgets.QPushButton(self._t("update_stream"))
        self.update_destination_button.clicked.connect(self._update_udp_destination)
        self.remove_destination_button = QtWidgets.QPushButton(self._t("remove"))
        self.remove_destination_button.clicked.connect(self._remove_udp_destination)
        self.destination_endpoint_label = QtWidgets.QLabel(self._t("endpoint"))
        self.destination_transport_label = QtWidgets.QLabel(self._t("transport"))
        self.destination_rate_label = QtWidgets.QLabel(self._t("output_rate"))
        self.destination_datagram_label = QtWidgets.QLabel(self._t("datagram"))
        self.destination_queue_label = QtWidgets.QLabel(self._t("queue"))
        destination_controls.addWidget(self.destination_endpoint_label, 0, 0)
        destination_controls.addWidget(self.destination_edit, 0, 1)
        destination_controls.addWidget(self.destination_transport_label, 0, 2)
        destination_controls.addWidget(self.destination_transport, 0, 3)
        destination_controls.addWidget(self.destination_rate_label, 1, 0)
        destination_controls.addWidget(self.destination_rate, 1, 1)
        destination_controls.addWidget(self.destination_datagram_label, 1, 2)
        destination_controls.addWidget(self.destination_datagram, 1, 3)
        destination_controls.addWidget(self.destination_queue_label, 1, 4)
        destination_controls.addWidget(self.destination_queue, 1, 5)
        destination_controls.addWidget(self.add_destination_button, 2, 3)
        destination_controls.addWidget(self.update_destination_button, 2, 4)
        destination_controls.addWidget(self.remove_destination_button, 2, 5)
        layout.addWidget(self.destination_editor)
        self.udp_note_label = QtWidgets.QLabel(self._t("udp_note"))
        self.udp_note_label.setProperty("role", "muted"); self.udp_note_label.setWordWrap(True); layout.addWidget(self.udp_note_label)
        if self.runtime is None or not hasattr(self.runtime, "add_udp_destination"):
            self.add_destination_button.setEnabled(False); self.update_destination_button.setEnabled(False); self.remove_destination_button.setEnabled(False)
        self._lan_udp_enabled = bool(getattr(self.runtime, "lan_udp_enabled", False))
        self.native_network_label = QtWidgets.QLabel(
            self._t("lan_udp_enabled") if self._lan_udp_enabled else self._t("lan_udp_disabled")
        )
        layout.addWidget(self.native_network_label)
        return tab

    def _consumer_selected(self) -> None:
        row = self.consumer_table.currentRow()
        if row < 0:
            return
        endpoint_item = self.consumer_table.item(row, 0)
        type_item = self.consumer_table.item(row, 1)
        if endpoint_item is None or type_item is None or type_item.text() != "UDP":
            return
        for destination_row in range(self.destinations_table.rowCount()):
            item = self.destinations_table.item(destination_row, 0)
            if item is not None and item.text() == endpoint_item.text():
                self.destinations_table.selectRow(destination_row)
                return

    def _add_udp_destination(self) -> None:
        if self.runtime is None or not hasattr(self.runtime, "add_udp_destination"):
            self._show_error(self._t("udp_management_unavailable"))
            return
        try:
            self._destination_endpoint_changed()
            self.runtime.add_udp_destination(
                self.destination_edit.text().strip(), self.destination_transport.currentData(),
                self.destination_rate.value(), self.destination_datagram.value(),
                self.destination_queue.value(),
            )
            self._show_error("")
            self.refresh()
        except Exception as exc:
            self._show_error(self._t("client_rejected").format(error=exc))

    def _destination_endpoint_changed(self) -> None:
        if self.destination_transport.currentData() == "qmap_linrad":
            return
        endpoint = self.destination_edit.text().strip()
        try:
            host, _ = endpoint.rsplit(":", 1)
        except ValueError:
            return
        if host.lower() not in {"127.0.0.1", "localhost", "::1"} and self.destination_datagram.value() == 8192:
            self.destination_datagram.setValue(1200)

    def _destination_transport_changed(self) -> None:
        qmap = self.destination_transport.currentData() == "qmap_linrad"
        if qmap:
            self.destination_rate.setValue(96_000)
            self.destination_datagram.setValue(1416)
        self.destination_rate.setEnabled(not qmap)
        self.destination_datagram.setEnabled(not qmap)

    def _destination_selected(self) -> None:
        row = self.destinations_table.currentRow()
        if row < 0 or self.destinations_table.item(row, 0) is None:
            return
        self.destination_edit.setText(self.destinations_table.item(row, 0).text())
        transport = self.destinations_table.item(row, 1).text()
        index = self.destination_transport.findData(transport)
        if index >= 0:
            self.destination_transport.setCurrentIndex(index)
        for column, control in ((2, self.destination_rate), (3, self.destination_datagram), (4, self.destination_queue)):
            item = self.destinations_table.item(row, column)
            if item is not None:
                control.setValue(int(item.text()))

    def _update_udp_destination(self) -> None:
        if self.runtime is None or not hasattr(self.runtime, "update_udp_destination"):
            self._show_error(self._t("udp_update_unavailable"))
            return
        row = self.destinations_table.currentRow()
        if row < 0 or self.destinations_table.item(row, 0) is None:
            self._show_error(self._t("select_udp_first"))
            return
        selected_endpoint = self.destinations_table.item(row, 0).text()
        if self.destination_edit.text().strip() != selected_endpoint:
            self._show_error(self._t("endpoint_immutable"))
            return
        try:
            self.runtime.update_udp_destination(
                selected_endpoint, self.destination_transport.currentData(),
                self.destination_rate.value(), self.destination_datagram.value(),
                self.destination_queue.value(),
            )
            self._show_error("")
            self.refresh()
        except Exception as exc:
            self._show_error(self._t("client_update_failed").format(error=exc))

    def _remove_udp_destination(self) -> None:
        if self.runtime is None or not hasattr(self.runtime, "remove_udp_destination"):
            self._show_error(self._t("udp_management_unavailable"))
            return
        row = self.destinations_table.currentRow()
        if row < 0 or self.destinations_table.item(row, 0) is None:
            self._show_error(self._t("select_udp_first"))
            return
        try:
            self.runtime.remove_udp_destination(self.destinations_table.item(row, 0).text())
            self._show_error("")
            self.refresh()
        except Exception as exc:
            self._show_error(self._t("client_removal_failed").format(error=exc))

    def _rf_tab(self) -> QtWidgets.QWidget:
        tab = QtWidgets.QWidget(); layout = QtWidgets.QVBoxLayout(tab); layout.setSpacing(10)
        auto_card = QtWidgets.QFrame(); auto_card.setProperty("card", True); auto_layout = QtWidgets.QHBoxLayout(auto_card)
        auto_text = QtWidgets.QVBoxLayout()
        self.rf_automatic_title = QtWidgets.QLabel(self._t("automatic_mode")); self.rf_automatic_title.setProperty("role", "sectionTitle")
        self.rf_auto_status = QtWidgets.QLabel(); self.rf_auto_status.setProperty("role", "metricValue")
        auto_text.addWidget(self.rf_automatic_title); auto_text.addWidget(self.rf_auto_status)
        auto_layout.addLayout(auto_text); auto_layout.addStretch(1)
        self.resume_rf_button = QtWidgets.QPushButton(self._t("resume_auto")); self.resume_rf_button.clicked.connect(self._resume_rf_auto)
        auto_layout.addWidget(self.resume_rf_button); layout.addWidget(auto_card)

        controls = QtWidgets.QHBoxLayout()
        self.rf_rules_title = QtWidgets.QLabel(self._t("rf_rules")); self.rf_rules_title.setProperty("role", "sectionTitle")
        controls.addWidget(self.rf_rules_title); controls.addStretch(1)
        self.new_rf_rule_button = QtWidgets.QPushButton(self._t("new_rule")); self.new_rf_rule_button.clicked.connect(self._new_rf_rule)
        self.edit_rf_rule_button = QtWidgets.QPushButton(self._t("edit")); self.edit_rf_rule_button.clicked.connect(self._edit_rf_rule)
        self.remove_rf_rule_button = QtWidgets.QPushButton(self._t("remove")); self.remove_rf_rule_button.clicked.connect(self._remove_rf_rule)
        controls.addWidget(self.new_rf_rule_button); controls.addWidget(self.edit_rf_rule_button); controls.addWidget(self.remove_rf_rule_button)
        layout.addLayout(controls)
        self.rf_rules_table = QtWidgets.QTableWidget(0, 10)
        self.rf_rules_table.setHorizontalHeaderLabels([self._t(key) for key in (
            "rule", "min_mhz", "max_mhz", "priority", "antenna", "agc", "if_rf", "bandwidth", "hysteresis", "state",
        )])
        self.rf_rules_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.rf_rules_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.rf_rules_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.rf_rules_table.doubleClicked.connect(lambda _index: self._edit_rf_rule())
        layout.addWidget(self.rf_rules_table, 1)
        self.rf_note_label = QtWidgets.QLabel(self._t("rf_note"))
        self.rf_note_label.setWordWrap(True); self.rf_note_label.setProperty("role", "muted"); layout.addWidget(self.rf_note_label)
        self._refresh_rf_rules()
        return tab

    def _selected_rf_rule(self) -> RFRule | None:
        row = self.rf_rules_table.currentRow()
        if row < 0 or self.rf_rules_table.item(row, 0) is None:
            return None
        rule_id = self.rf_rules_table.item(row, 0).text()
        return next((rule for rule in self.rf_profiles.rules if rule.rule_id == rule_id), None)

    def _new_rf_rule(self) -> None:
        self._show_rf_rule_dialog(None)

    def _edit_rf_rule(self) -> None:
        rule = self._selected_rf_rule()
        if rule is not None:
            self._show_rf_rule_dialog(rule)

    def _show_rf_rule_dialog(self, rule: RFRule | None) -> None:
        dialog = RFRuleDialog(self._capabilities, self.bridge.device_id, rule, self, language=self.language)
        dialog.setStyleSheet(DARK_STYLESHEET)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        try:
            updated = dialog.rule()
            if rule is not None and rule.rule_id != updated.rule_id:
                self.rf_profiles.remove(rule.rule_id)
            self.rf_profiles.replace(updated)
            self._save_rf_profiles(); self._refresh_rf_rules()
            if not self.rf_profiles.suspended:
                self._apply_rf_profile(self.frequency_control.value_hz())
            self._show_error("")
        except Exception as exc:
            self._show_error(self._t("rf_rule_rejected").format(error=exc))

    def _remove_rf_rule(self) -> None:
        rule = self._selected_rf_rule()
        if rule is None:
            return
        self.rf_profiles.remove(rule.rule_id)
        if self._active_rf_rule_id == rule.rule_id:
            self._active_rf_rule_id = None
        self._save_rf_profiles(); self._refresh_rf_rules()

    def _resume_rf_auto(self) -> None:
        self.auto_table_check.setChecked(True)

    def _refresh_rf_rules(self) -> None:
        if not hasattr(self, "rf_rules_table"):
            return
        rules = self.rf_profiles.rules
        self.rf_rules_table.setRowCount(len(rules))
        for row, rule in enumerate(rules):
            gains = " / ".join(f"{name}={value:g}" for name, value in rule.gains.items()) or "—"
            values = (
                rule.rule_id, f"{rule.min_hz / 1e6:.6f}", f"{rule.max_hz / 1e6:.6f}", rule.priority,
                rule.antenna or "—", self._t("keep") if rule.agc_enabled is None else ("ON" if rule.agc_enabled else "OFF"),
                gains, "—" if rule.bandwidth_hz is None else f"{rule.bandwidth_hz / 1e6:.3f} MHz",
                f"{rule.hysteresis_hz / 1000:g} kHz", self._t("active_upper") if rule.rule_id == self._active_rf_rule_id else (self._t("enabled") if rule.enabled else self._t("disabled")),
            )
            for column, value in enumerate(values):
                self.rf_rules_table.setItem(row, column, QtWidgets.QTableWidgetItem(str(value)))
        suspended = self.rf_profiles.suspended
        self.rf_auto_status.setText(self._t("manual_override") if suspended else self._t("auto_enabled"))
        self.rf_auto_status.setProperty("role", "warning" if suspended else "success")
        self.resume_rf_button.setVisible(suspended)
        self.rf_rules_table.setToolTip(self._t("no_rules") if not rules else "")

    def _apply_rf_profile(self, frequency_hz: int) -> None:
        rule = self.rf_profiles.select(frequency_hz, str(self.bridge.device_id or ""), self._active_rf_rule_id)
        new_id = None if rule is None else rule.rule_id
        if new_id == self._active_rf_rule_id:
            return
        self._active_rf_rule_id = new_id
        if rule is None:
            self._refresh_rf_rules()
            return
        self._applying_rf_profile = True
        try:
            if rule.antenna is not None:
                index = self.antenna_combo.findData(rule.antenna)
                if index >= 0:
                    self.antenna_combo.setCurrentIndex(index)
            if rule.bandwidth_hz is not None:
                index = next(
                    (
                        candidate for candidate in range(1, self.bandwidth_combo.count())
                        if self.bandwidth_combo.itemData(candidate) == rule.bandwidth_hz
                    ),
                    -1,
                )
                if index >= 0:
                    self.bandwidth_combo.setCurrentIndex(index)
            if rule.agc_enabled is not None:
                self.agc_check.setChecked(rule.agc_enabled)
            for slot, slider in enumerate((self.if_gain_slider, self.rf_gain_slider)):
                name = self._primary_gain_names[slot]
                legacy_name = "gain_reduction_db" if slot == 0 else "lna_state"
                if name in rule.gains:
                    slider.setValue(round(rule.gains[name]))
                elif legacy_name in rule.gains:
                    slider.setValue(round(rule.gains[legacy_name]))
            for name, value in rule.gains.items():
                control = self.extra_gain_controls.get(name)
                if control is not None:
                    if isinstance(control, QtWidgets.QCheckBox):
                        control.setChecked(bool(value))
                    elif isinstance(control, QtWidgets.QComboBox):
                        index = control.findData(value)
                        if index >= 0:
                            control.setCurrentIndex(index)
                    else:
                        control.setValue(round(value))
        finally:
            self._applying_rf_profile = False
        self._refresh_rf_rules()

    def _capture_tab(self) -> QtWidgets.QWidget:
        tab = QtWidgets.QWidget(); layout = QtWidgets.QVBoxLayout(tab); layout.setSpacing(10)
        self.capture_directory = Path.cwd() / "Captures"
        self.capture_directory.mkdir(parents=True, exist_ok=True)
        metrics = QtWidgets.QHBoxLayout()
        self.capture_volume_card, self.capture_volume_title, self.capture_volume_label = self._metric_card("recorded_volume")
        self.capture_rate_card, self.capture_rate_title, self.capture_rate_label = self._metric_card("measured_rate")
        self.capture_source_card, self.capture_source_title, self.capture_source_label = self._metric_card("recorded_source")
        self.capture_integrity_card, self.capture_integrity_title, self.capture_integrity_label = self._metric_card("integrity")
        for card in (self.capture_volume_card, self.capture_rate_card, self.capture_source_card, self.capture_integrity_card):
            metrics.addWidget(card)
        metrics.addStretch(1); layout.addLayout(metrics)
        self.capture_group = QtWidgets.QGroupBox(self._t("recording_config")); form = QtWidgets.QFormLayout(self.capture_group)
        self.capture_format_combo = QtWidgets.QComboBox()
        self.capture_format_combo.addItem("SigMF 1.2.6", CaptureFormat.SIGMF.value)
        self.capture_format_combo.addItem(self._t("sdrpp_wav"), CaptureFormat.SDRPP_WAV.value)
        self.capture_format_combo.addItem(self._t("hdsdr_wav"), CaptureFormat.HDSDR_WAV.value)
        self.capture_path = QtWidgets.QLineEdit(str(self.capture_directory))
        self.capture_path.setReadOnly(True)
        self.capture_profile = QtWidgets.QComboBox()
        for profile in self.bridge.profiles.items():
            if profile.protocol in {"ring_v2", "sdbu_v2"}:
                self.capture_profile.addItem(profile.name or profile.profile_id, (profile.profile_id, profile.profile_revision))
        self.capture_button = QtWidgets.QPushButton(self._t("start_capture"))
        self.capture_button.clicked.connect(self._toggle_capture)
        self.capture_button.setProperty("success", True)
        self.open_capture_folder_button = QtWidgets.QPushButton(self._t("open_folder")); self.open_capture_folder_button.clicked.connect(self._open_capture_folder)
        self.capture_status = QtWidgets.QLabel(self._t("recorder_stopped"))
        self.capture_format_label = QtWidgets.QLabel(self._t("format")); form.addRow(self.capture_format_label, self.capture_format_combo)
        self.capture_profile_label = QtWidgets.QLabel(self._t("iq_profile")); form.addRow(self.capture_profile_label, self.capture_profile)
        self.capture_output_label = QtWidgets.QLabel(self._t("output_file")); form.addRow(self.capture_output_label, self.capture_path)
        buttons = QtWidgets.QHBoxLayout(); buttons.addWidget(self.capture_button); buttons.addWidget(self.open_capture_folder_button); buttons.addStretch(1)
        form.addRow(buttons); form.addRow(self.capture_status); layout.addWidget(self.capture_group)
        self.capture_note_label = QtWidgets.QLabel(self._t("capture_note"))
        self.capture_note_label.setWordWrap(True); self.capture_note_label.setProperty("role", "muted"); layout.addWidget(self.capture_note_label); layout.addStretch(1)
        return tab

    def _open_capture_folder(self) -> None:
        self.capture_directory.mkdir(parents=True, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(self.capture_directory)))

    def _build_diagnostics_dialog(self) -> None:
        self.diagnostics_dialog = QtWidgets.QDialog(self)
        self.diagnostics_dialog.setWindowTitle(self._t("diagnostics_title"))
        self.diagnostics_dialog.resize(820, 620)
        layout = QtWidgets.QVBoxLayout(self.diagnostics_dialog)
        self.diagnostics_title = QtWidgets.QLabel(self._t("system_diagnostics")); self.diagnostics_title.setProperty("role", "sectionTitle"); layout.addWidget(self.diagnostics_title)
        self.diagnostics = QtWidgets.QPlainTextEdit(); self.diagnostics.setReadOnly(True)
        layout.addWidget(self.diagnostics)
        buttons = QtWidgets.QDialogButtonBox()
        self.diagnostics_copy_button = buttons.addButton(self._t("copy_json"), QtWidgets.QDialogButtonBox.ActionRole)
        self.diagnostics_export_button = buttons.addButton(self._t("export_diagnostics"), QtWidgets.QDialogButtonBox.ActionRole)
        self.diagnostics_close_button = buttons.addButton(self._t("close"), QtWidgets.QDialogButtonBox.RejectRole)
        self.diagnostics_copy_button.clicked.connect(self._copy_diagnostics)
        self.diagnostics_export_button.clicked.connect(self._export_diagnostics)
        self.diagnostics_close_button.clicked.connect(self.diagnostics_dialog.close)
        layout.addWidget(buttons)

    def _build_compact(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget(); layout = QtWidgets.QVBoxLayout(page); layout.setContentsMargins(8, 5, 8, 5); layout.setSpacing(3)
        top = QtWidgets.QHBoxLayout()
        # Compatibility alias kept for automation, but the compact operator
        # view deliberately starts with the frequency and no duplicated state.
        self.compact_state = QtWidgets.QLabel(""); self.compact_state.hide()
        self.compact_frequency = QtWidgets.QLabel("— Hz"); self.compact_frequency.setProperty("role", "metricValue")
        self.compact_frequency.setMinimumWidth(128)
        self.compact_consumers = QtWidgets.QLabel(self._t("consumers_count").format(count=0))
        self.compact_consumers.setProperty("role", "muted")
        self.normal_view_button = QtWidgets.QToolButton(); self.normal_view_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_TitleBarNormalButton)); self.normal_view_button.setToolTip(self._t("normal_view")); self.normal_view_button.clicked.connect(self.toggle_compact)
        self.always_on_top = QtWidgets.QCheckBox(self._t("top")); self.always_on_top.setToolTip(self._t("always_on_top")); self.always_on_top.toggled.connect(self._always_on_top)
        self.compact_rx_button = QtWidgets.QToolButton()
        self.compact_rx_button.setAccessibleName(self._t("start_stop_sdr"))
        self.compact_rx_button.clicked.connect(self._toggle_rx)
        self.compact_rx_button.setFixedSize(40, 40)
        self.compact_stop_button = self.compact_rx_button  # compatibility alias
        top.addWidget(self.compact_frequency); top.addWidget(self.compact_consumers); top.addStretch(1); top.addWidget(self.always_on_top); top.addWidget(self.compact_rx_button); top.addWidget(self.normal_view_button)
        layout.addLayout(top)
        self.compact_plot_stack = QtWidgets.QStackedWidget()
        self.compact_plot = self._new_plot(True); self.compact_curve = self.compact_plot.plot(pen=pg.mkPen("#37D7FF", width=1.2), fillLevel=-120, brush=pg.mkBrush(15, 130, 190, 70)); self.compact_plot_stack.addWidget(self.compact_plot)
        self.compact_waterfall_plot, self.compact_waterfall_image = self._new_waterfall_plot(True); self.compact_plot_stack.addWidget(self.compact_waterfall_plot)
        compact_split = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.compact_split_plot = self._new_plot(True); self.compact_split_curve = self.compact_split_plot.plot(pen=pg.mkPen("#37D7FF", width=1.0))
        self.compact_split_waterfall_plot, self.compact_split_waterfall_image = self._new_waterfall_plot(True)
        compact_split.addWidget(self.compact_split_plot); compact_split.addWidget(self.compact_split_waterfall_plot); self.compact_plot_stack.addWidget(compact_split)
        layout.addWidget(self.compact_plot_stack, 1)
        self.compact_stats = QtWidgets.QLabel(""); self.compact_stats.hide()
        self._set_plot_mode(self._plot_mode)
        return page

    def _draw_spectrum(self, frequencies, db) -> None:
        compact = self._stack.currentIndex() == 1
        if self._plot_mode == "spectrum":
            curve = self.compact_curve if compact else self.normal_curve
            curve.setData(frequencies, db)
        elif self._plot_mode == "split":
            curve = self.compact_split_curve if compact else self.split_spectrum_curve
            curve.setData(frequencies, db)
        waterfall_db = np.asarray(db, dtype=np.float32)
        waterfall_frequencies = np.asarray(frequencies)
        if len(waterfall_db) > 1024:
            # More columns than the plot has physical pixels only increase
            # Qt image upload/copy cost. Max pooling preserves narrow peaks.
            group = int(np.ceil(len(waterfall_db) / 1024))
            usable = len(waterfall_db) - (len(waterfall_db) % group)
            if usable:
                waterfall_db = waterfall_db[:usable].reshape(-1, group).max(axis=1)
                waterfall_frequencies = waterfall_frequencies[:usable:group]
        if self._waterfall is None or self._waterfall.shape[1] != len(waterfall_db):
            self._waterfall = np.full((self._waterfall_rows, len(waterfall_db)), -120.0, dtype=np.float32)
        if self._plot_mode in {"waterfall", "split"}:
            self._waterfall[:-1] = self._waterfall[1:]
            self._waterfall[-1] = waterfall_db
        if self._plot_mode in {"waterfall", "split"} and len(waterfall_frequencies) > 1:
            rect = QtCore.QRectF(
                float(frequencies[0]), 0.0,
                float(frequencies[-1] - frequencies[0]),
                float(self._waterfall_rows),
            )
            if compact:
                image = self.compact_waterfall_image if self._plot_mode == "waterfall" else self.compact_split_waterfall_image
            else:
                image = self.waterfall_image if self._plot_mode == "waterfall" else self.split_waterfall_image
            image.setImage(
                self._waterfall,
                autoLevels=False,
                levels=(self.y_min_slider.value(), self.y_max_slider.value()),
            )
            image.setRect(rect)
            if self._plot_mode == "split":
                low, high = float(frequencies[0]), float(frequencies[-1])
                spectrum_plot = self.compact_split_plot if compact else self.split_spectrum_plot
                waterfall_plot = self.compact_split_waterfall_plot if compact else self.split_waterfall_plot
                # The ImageItem's auto-range can otherwise differ from the
                # curve range. Apply one explicit frequency window after the
                # image transform so both sets of ticks line up exactly.
                spectrum_plot.setXRange(low, high, padding=0)
                waterfall_plot.setXRange(low, high, padding=0)

    def _stream_state(self, active: bool) -> None:
        if not active and self.bridge.running:
            self.status_bar.setText(self._t("rx_waiting"))
            self.normal_curve.setPen(pg.mkPen("#6b7780")); self.compact_curve.setPen(pg.mkPen("#6b7780"))
        else:
            self.normal_curve.setPen(pg.mkPen("#37D7FF")); self.compact_curve.setPen(pg.mkPen("#37D7FF"))

    def _show_error(self, text: str) -> None:
        self.error_banner.setText(text); self.error_banner.setVisible(bool(text))

    def _toggle_rx(self) -> None:
        if self._rx_action_busy:
            return
        state = self.bridge.state
        if state in {LifecycleState.OPENING, LifecycleState.STARTING, LifecycleState.STOPPING, LifecycleState.RECOVERING}:
            return
        target_running = not self.bridge.running
        self._rx_action_busy = True
        self._rx_action_target_running = target_running
        self._show_error("")
        self.refresh()

        def worker() -> None:
            error = None
            try:
                if target_running:
                    self.bridge.start()
                else:
                    self.bridge.stop()
            except BaseException as exc:  # passed back to the Qt main thread
                error = exc
            self.rxActionFinished.emit(error)

        threading.Thread(target=worker, name="sdr-rx-action", daemon=True).start()

    @QtCore.pyqtSlot(object)
    def _rx_action_finished(self, error) -> None:
        target_running = self._rx_action_target_running
        self._rx_action_busy = False
        self._rx_action_target_running = None
        if error is None:
            if target_running:
                self.spectrum.resync_after_reconfigure()
            self._show_error("")
        else:
            self._show_error(str(error))
        self.refresh()

    def _stop_rx(self) -> None:
        if self.bridge.running and not self._rx_action_busy:
            self._toggle_rx()

    @staticmethod
    def _set_button_state(button: QtWidgets.QAbstractButton, *, running: bool, pending: bool) -> None:
        button.setProperty("success", bool(running and not pending))
        button.setProperty("pending", bool(pending))
        button.setEnabled(not pending)
        button.style().unpolish(button)
        button.style().polish(button)

    def _refresh_rx_buttons(self, state: str) -> None:
        transitional = state in {"OPENING", "STARTING", "STOPPING", "RECOVERING"}
        pending = bool(self._rx_action_busy or transitional)
        target_running = self._rx_action_target_running
        if target_running is None:
            target_running = state in {"OPENING", "STARTING", "RECOVERING", "RUNNING"}
        running = state == "RUNNING"
        icon = self._stop_icon if running or (pending and not target_running) else self._play_icon
        if pending:
            text_key = "acquisition_starting" if target_running else "acquisition_stopping"
            tooltip = self._t(text_key)
        else:
            text_key = "acquisition_active" if running else "acquisition_stopped"
            tooltip = self._t("stop_sdr") if running else self._t("start_sdr")
        self.start_button.setIcon(icon)
        self.start_button.setText(self._t(text_key))
        self.start_button.setToolTip(tooltip)
        self.compact_rx_button.setIcon(icon)
        self.compact_rx_button.setToolTip(tooltip)
        self._set_button_state(self.start_button, running=running, pending=pending)
        self._set_button_state(self.compact_rx_button, running=running, pending=pending)

    def _apply_config(self) -> None:
        try:
            requested = self._draft_config()
        except Exception as exc:
            self._show_error(self._t("configuration_rejected").format(error=exc))
            self.refresh()
            return
        if self._config_apply_busy:
            # Un déplacement de slider peut produire plusieurs événements.
            # On ne garde que le dernier brouillon, jamais une file de mises
            # à jour obsolètes.
            self._config_apply_pending = requested
            return
        self._config_apply_busy = True
        self.status_bar.setText(self._t("applying_update"))

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
        gains = {name: self._control_value(control) for name, control in self.extra_gain_controls.items()}
        for name, slider in zip(self._primary_gain_names, (self.if_gain_slider, self.rf_gain_slider)):
            if name:
                gains[name] = int(slider.value())
        return {
            "center_frequency_hz": int(self.frequency_edit.text()),
            "sample_rate_sps": int(self.rate_edit.text()),
            "bandwidth_hz": int(self.bandwidth_edit.text()),
            "gain_reduction_db": int(self.gain_edit.text()),
            "agc_enabled": self.agc_check.isChecked(),
            "antenna": self.antenna_combo.currentData() or None,
            "gains": gains,
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
            self._show_error(self._t("stale_config"))
        else:
            self._show_error(self._t("configuration_rejected").format(error=error))
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

    def _capture_default_path(self, capture_format: CaptureFormat) -> Path:
        timestamp = datetime.now(timezone.utc)
        frequency_hz = int(self.bridge.config.center_frequency_hz)
        if capture_format is CaptureFormat.SDRPP_WAV:
            name = f"baseband_{frequency_hz}Hz_{timestamp:%H-%M-%S_%d-%m-%Y}.wav"
        elif capture_format is CaptureFormat.HDSDR_WAV:
            name = f"HDSDR_{timestamp:%Y%m%d_%H%M%SZ}_{frequency_hz / 1000:g}kHz_RF.wav"
        else:
            name = f"SDRbridge_{timestamp:%Y%m%d_%H%M%SZ}_{frequency_hz}Hz.sigmf-meta"
        return self.capture_directory / name

    def _choose_capture_path(self, capture_format: CaptureFormat) -> str | None:
        self.capture_directory.mkdir(parents=True, exist_ok=True)
        file_filter = (
            self._t("sigmf_filter")
            if capture_format is CaptureFormat.SIGMF
            else self._t("wave_iq_filter")
        )
        selected, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            self._t("save_capture"),
            str(self._capture_default_path(capture_format)),
            file_filter,
        )
        if not selected:
            return None
        self.capture_directory = Path(selected).parent
        return selected

    def _toggle_capture(self) -> None:
        if self.runtime is None:
            self._show_error(self._t("recorder_unavailable"))
            return
        try:
            if self.runtime.recorder is None:
                capture_format = CaptureFormat(self.capture_format_combo.currentData())
                output_path = self._choose_capture_path(capture_format)
                if output_path is None:
                    return
                profile_id, revision = self.capture_profile.currentData()
                actual_path = self.runtime.start_recording(
                    output_path,
                    profile_id,
                    revision,
                    capture_format,
                )
                self.capture_path.setText(str(actual_path))
            else:
                self.runtime.stop_recording("operator stop")
            self._show_error("")
        except Exception as exc:
            self._show_error(str(exc))
        self.refresh()

    def toggle_compact(self) -> None:
        if self._stack.currentIndex() == 0:
            self._normal_geometry = self.saveGeometry()
            self._stack.setCurrentIndex(1); self.setMinimumSize(360, 100); self.resize(396, 112)
        else:
            self._stack.setCurrentIndex(0); self.setMinimumSize(980, 640)
            if self._normal_geometry:
                self.restoreGeometry(self._normal_geometry)
            else:
                self.resize(1280, 800)

    def _always_on_top(self, enabled: bool) -> None:
        self.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, enabled)
        self.show()

    def refresh(self) -> None:
        status = self.bridge.status(); cfg = status["config"]; state = status["state"]
        connected = state == "RUNNING"
        source_name = status["source"]
        source_short = source_name
        is_file_source = source_name.lower().startswith("fichier iq") or str(status.get("source_id", "")).startswith("file:")
        is_simulated_source = "simulat" in source_name.lower()
        if is_file_source:
            source_short = self._t("iq_file")
        elif is_simulated_source:
            source_short = self._t("simulation")
        self.state_label.setText(source_short)
        color = "#39d98a" if connected else ("#ff6b7a" if state == "ERROR" else "#8899a8")
        self.state_label.setStyleSheet(f"font-weight:bold;color:{color}")
        frequency = f"{cfg['center_frequency_hz']:,} Hz".replace(",", " ")
        self.frequency_effective.setText(frequency); self.compact_frequency.setText(frequency)
        self._update_frequency_axes(cfg["center_frequency_hz"])
        self._refresh_rx_buttons(state)
        needs_capabilities = bool(
            self.bridge.device_id
            and not str(self.bridge.device_id).startswith("file:")
            and not self._capabilities
            and self._capability_refresh_attempts < 3
        )
        if self.device_combo.count() == 0 or needs_capabilities:
            self._capability_refresh_attempts += 1
            self._refresh_devices()
            if self.auto_table_check.isChecked():
                self._apply_rf_profile(int(cfg["center_frequency_hz"]))
        self.connection_label.setText(
            source_name if is_file_source else ("Simulation" if is_simulated_source else "")
        )
        disabled = state in {"OPENING", "RECONFIGURING", "STOPPING", "STARTING"}
        is_file = str(self.bridge.device_id or "").startswith("file:")
        self._set_hardware_controls_enabled(not is_file and not disabled)
        # Do not overwrite a freshly edited draft during the short debounce
        # interval before _apply_config() starts.  A 1 Hz refresh landing in
        # that 180 ms window previously restored the old rate/bandwidth and
        # made some hardware changes appear to be ignored.
        if not self._config_apply_busy and not self._live_apply_timer.isActive():
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
            values = (
                item["destination"], item["transport"],
                item.get("configured_sample_rate_sps") or item.get("last_sample_rate_sps") or "—",
                item.get("datagram_bytes") or "—", item.get("queue_blocks") or "—",
                item["sent_packets"], item["sent_bytes"], item["dropped_blocks"],
                item["socket_errors"], item.get("last_center_frequency_hz") or "—",
            )
            for column, value in enumerate(values):
                self.destinations_table.setItem(row, column, QtWidgets.QTableWidgetItem(str(value)))
        self.consumer_table.setRowCount(len(clients) + len(destinations))
        visible_row = 0
        for client in clients:
            values = (
                client["name"], self._t("local"), "ring_v2", f"{cfg['sample_rate_sps']:,}".replace(",", " "),
                "—", "—", client["blocks_read"], client["dropped_blocks"], self._t("active") if connected else self._t("idle"),
            )
            for column, value in enumerate(values):
                self.consumer_table.setItem(visible_row, column, QtWidgets.QTableWidgetItem(str(value)))
            visible_row += 1
        for item in destinations:
            output_rate = item.get("configured_sample_rate_sps") or item.get("last_sample_rate_sps") or 0
            values = (
                item["destination"], "UDP", item["transport"], f"{int(output_rate):,}".replace(",", " ") if output_rate else "—",
                item.get("datagram_bytes") or "—", item.get("queue_blocks") or "—", item["sent_packets"],
                int(item["dropped_blocks"]) + int(item["socket_errors"]), self._t("streaming") if connected else self._t("idle"),
            )
            for column, value in enumerate(values):
                self.consumer_table.setItem(visible_row, column, QtWidgets.QTableWidgetItem(str(value)))
            visible_row += 1

        consumer_count = len(clients) + len(destinations)
        useful_udp_bps = sum(int(item.get("configured_sample_rate_sps") or item.get("last_sample_rate_sps") or 0) * 32 for item in destinations)
        logical_bps = useful_udp_bps + len(clients) * int(cfg["sample_rate_sps"]) * 32
        total_sent = sum(int(item.get("sent_bytes", 0)) for item in destinations)
        now = time.monotonic(); elapsed = max(now - self._last_udp_sample_at, 1e-3)
        if total_sent >= self._last_udp_total:
            self._udp_wire_rate_bps = (total_sent - self._last_udp_total) * 8 / elapsed
        self._last_udp_total = total_sent; self._last_udp_sample_at = now
        acquisition_losses = (
            int(status["source_queue_drops"])
            + int(status.get("source_losses", 0))
            + int(status.get("dsp_queue_drops", 0))
            + int(status.get("profile_queue_drops", 0))
            + int(status["source_errors"])
            + int(status.get("dsp_errors", 0))
        )
        total_losses = acquisition_losses + sum(
            int(item["dropped_blocks"]) + int(item["socket_errors"])
            for item in destinations
        )
        self.measured_rate_label.setText(f"{status['sample_rate_measured']/1e6:.3f} MS/s")
        self.consumer_count_label.setText(str(consumer_count)); self.udp_rate_label.setText(f"{useful_udp_bps/1e6:.1f} Mb/s")
        self.loss_label.setText(str(total_losses))
        self._update_process_cpu_metric()
        self.stream_consumers_value.setText(str(consumer_count)); self.stream_logical_value.setText(f"{logical_bps/1e6:.1f} Mb/s")
        self.stream_network_value.setText(f"{self._udp_wire_rate_bps/1e6:.1f} Mb/s"); self.stream_loss_value.setText(str(total_losses))
        if self._rx_action_busy:
            pending_key = "acquisition_starting" if self._rx_action_target_running else "acquisition_stopping"
            self.status_bar.setText(self._t(pending_key))
        else:
            self.status_bar.setText(self._t("status_line").format(
                rate=status["sample_rate_measured"] / 1e6,
                drops=(
                    int(status["source_queue_drops"])
                    + int(status.get("source_losses", 0))
                    + int(status.get("dsp_queue_drops", 0))
                    + int(status.get("profile_queue_drops", 0))
                ),
                errors=int(status["source_errors"]) + int(status.get("dsp_errors", 0)),
            ))
        self.compact_stats.setText(self._t("compact_stats").format(count=consumer_count, drops=total_losses))
        self.compact_consumers.setText(self._t("consumers_count").format(count=consumer_count))
        recorder = getattr(self.runtime, "recorder", None)
        if recorder:
            self.capture_status.setText(
                self._t("capture_active").format(bytes=recorder.bytes_written, file=recorder.output_path.name)
            )
            self.capture_button.setText(self._t("stop_capture"))
            self.rec_top_label.setVisible(True)
            self.capture_format_combo.setEnabled(False)
            self.capture_profile.setEnabled(False)
            self.capture_volume_label.setText(f"{recorder.bytes_written / (1024**2):.1f} MiB")
            self.capture_rate_label.setText(f"{status['sample_rate_measured']/1e6:.3f} MS/s")
            self.capture_source_label.setText(source_short)
            self.capture_integrity_label.setText("OK" if total_losses == 0 else self._t("losses_count").format(count=total_losses))
        else:
            self.capture_status.setText(self._t("recorder_stopped"))
            self.capture_button.setText(self._t("start_capture"))
            self.rec_top_label.setVisible(False)
            self.capture_format_combo.setEnabled(True)
            self.capture_profile.setEnabled(True)
            self.capture_volume_label.setText("0 MiB"); self.capture_rate_label.setText("—")
            self.capture_source_label.setText("—"); self.capture_integrity_label.setText("—")
        self._refresh_rf_rules()
        diagnostics = {key: status[key] for key in (
            "state", "source", "source_id", "epoch", "blocks_received", "blocks_written",
            "source_queue_drops", "source_queue_capacity", "source_queue_high_water", "source_errors",
            "source_losses",
            "dispatch_processing_average_ms", "dispatch_processing_max_ms", "dispatch_slow_blocks",
            "dsp_queue_drops", "dsp_queue_capacity", "dsp_queue_high_water", "dsp_blocks_processed",
            "dsp_processing_average_ms", "dsp_processing_max_ms", "dsp_slow_blocks", "dsp_errors",
            "last_error", "pipelines",
        )}
        diagnostics["capabilities"] = self._capabilities
        diagnostics["process_cpu_percent_one_core"] = round(self._process_cpu_percent, 3)
        diagnostics["process_cpu_core_equivalents"] = round(self._process_cpu_percent / 100.0, 3)
        diagnostics["logical_cpu_count"] = self._logical_cpu_count
        diagnostics["log_file"] = str(self.runtime.log_path) if self.runtime is not None and getattr(self.runtime, "log_path", None) else None
        self.diagnostics.setPlainText(json.dumps(diagnostics, ensure_ascii=False, indent=2))

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        recorder_active = bool(getattr(self.runtime, "recorder", None))
        if self.bridge.running or recorder_active:
            question = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Question, self._t("quit_title"), self._t("quit_question"), parent=self)
            confirm_button = question.addButton(self._t("quit_confirm"), QtWidgets.QMessageBox.AcceptRole)
            cancel_button = question.addButton(self._t("cancel"), QtWidgets.QMessageBox.RejectRole)
            question.setDefaultButton(cancel_button)
            question.exec_()
            if question.clickedButton() is not confirm_button:
                event.ignore(); return
        # SDRplay teardown normally takes around one to two seconds. Make that
        # bounded wait explicit instead of leaving an apparently dead window.
        self.setWindowTitle(f"SDRbridge {__version__} — {self._t('shutting_down')}")
        self.setEnabled(False)
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        QtWidgets.QApplication.processEvents()
        self.spectrum.close()
        try:
            if self.runtime:
                self.runtime.close()
            else:
                self.bridge.close()
            event.accept()
        except Exception as exc:
            self.setEnabled(True)
            self._show_error(self._t("shutdown_failed").format(error=exc))
            event.ignore()
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()


def prepare_gui() -> QtWidgets.QApplication:
    """Load the bundled Qt runtime before a backend can alter DLL search paths."""
    if sys.platform == "win32":
        try:
            import ctypes

            # This identifier must match the installer shortcuts. Without the
            # matching shortcut metadata Windows can fall back to a generic
            # taskbar icon on a fresh PC even though the EXE has an icon.
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SDRbridge.SDRbridge")
        except (AttributeError, OSError):
            pass
    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    application.setApplicationName("SDRbridge")
    resource_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    icon_path = resource_root / "assets" / "branding" / "sdrbridge.ico"
    if icon_path.is_file():
        application.setWindowIcon(QtGui.QIcon(str(icon_path)))
    application.setStyle(SDRBridgeProxyStyle())
    return application


def run_gui(bridge: SDRBridge, runtime: Any | None = None) -> int:
    application = prepare_gui()
    window = BridgeWindow(bridge, runtime)
    window.setWindowIcon(application.windowIcon())
    window.show()
    return application.exec_()


BridgeGUI = BridgeWindow
