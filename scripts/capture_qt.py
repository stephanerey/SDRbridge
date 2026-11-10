from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5 import QtTest, QtWidgets

from sdr_bridge.bridge import SDRBridge
from sdr_bridge.gui import BridgeWindow, prepare_gui
from sdr_bridge.model import DeviceCapabilities, DeviceDescriptor, SampleFormat
from sdr_bridge.source import SimulatedSource


class VisualRSP1ASource(SimulatedSource):
    @property
    def name(self):
        return "SDRplay Dev0 RSP1A 2236027C98 (simulated visual proof)"

    def enumerate(self):
        return [DeviceDescriptor(self.DEVICE_ID, "soapy/sdrplay", self.name, "2236027C98")]

    def capabilities(self, device_id):
        if device_id != self.DEVICE_ID:
            raise KeyError(device_id)
        return DeviceCapabilities(
            device_id, ((1_000, 2_000_000_000),), (2_000_000, 6_000_000, 8_000_000, 10_000_000),
            (200_000, 300_000, 600_000, 1_536_000, 5_000_000, 6_000_000, 7_000_000, 8_000_000),
            ("RX",), {"IFGR": (20, 59), "RFGR": (0, 9)}, True, (SampleFormat.CS16,), 1,
            (), (), {"IFGR": 40, "RFGR": 3}, {"IFGR": 1, "RFGR": 1},
        )


class CaptureRuntime:
    instance_name = "visual-qa"
    native_control = None
    operator_udp = None
    recorder = None
    log_path = None
    iq_file_path = None

    def __init__(self, bridge):
        self.bridge = bridge

    def udp_destinations_snapshot(self):
        common = {
            "sent_packets": 1234, "sent_bytes": 8_192_000,
            "dropped_blocks": 0, "socket_errors": 0,
            "last_center_frequency_hz": 144_300_000,
        }
        return [
            {**common, "destination": "127.0.0.1:7355", "transport": "sdbu_v2", "configured_sample_rate_sps": 2_000_000, "datagram_bytes": 8192, "queue_blocks": 32},
            {**common, "destination": "127.0.0.1:7356", "transport": "sdrpp_raw_cs16", "configured_sample_rate_sps": 192_000, "datagram_bytes": 8192, "queue_blocks": 64},
            {**common, "destination": "127.0.0.1:7357", "transport": "sdbu_v2", "configured_sample_rate_sps": 1_000_000, "datagram_bytes": 8192, "queue_blocks": 32},
        ]

    def available_sources(self):
        return self.bridge.enumerate_devices()

    def select_iq_file(self, *_args, **_kwargs):
        pass

    def select_source_device(self, device_id):
        self.bridge.select_device(device_id)

    def set_iq_file_loop(self, _enabled):
        pass

    def add_udp_destination(self, *_args):
        pass

    def update_udp_destination(self, *_args):
        pass

    def remove_udp_destination(self, *_args):
        pass

    def close(self):
        pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--language", choices=("en", "fr"), default="en")
    args = parser.parse_args()
    output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
    app = prepare_gui()
    bridge = SDRBridge(VisualRSP1ASource(block_samples=4096), block_samples=4096)
    bridge.start()
    window = BridgeWindow(bridge, CaptureRuntime(bridge)); window.language = args.language; window._retranslate_ui(); window.show(); QtTest.QTest.qWait(300)
    normal_size = [window.width(), window.height()]
    normal = output / "radio-spectrum.png"; window.grab().save(str(normal))
    window._set_plot_mode("waterfall"); QtTest.QTest.qWait(100)
    waterfall = output / "radio-waterfall.png"; window.grab().save(str(waterfall))
    window.tabs.setCurrentIndex(1); QtTest.QTest.qWait(100)
    outputs = output / "clients-streams.png"; window.grab().save(str(outputs))
    window.tabs.setCurrentIndex(2); QtTest.QTest.qWait(100)
    rf_profiles = output / "rf-profiles.png"; window.grab().save(str(rf_profiles))
    window.tabs.setCurrentIndex(3); QtTest.QTest.qWait(100)
    captures = output / "captures.png"; window.grab().save(str(captures))
    window.tabs.setCurrentIndex(0); window._set_plot_mode("spectrum")
    before = bridge.blocks_written; window.toggle_compact(); QtTest.QTest.qWait(200)
    compact = output / "compact.png"; window.grab().save(str(compact))
    after = bridge.blocks_written
    report = {
        "platform": os.environ.get("QT_QPA_PLATFORM"),
        "scale_factor": os.environ.get("QT_SCALE_FACTOR", "1"),
        "language": args.language,
        "normal": str(normal.resolve()),
        "waterfall": str(waterfall.resolve()),
        "compact": str(compact.resolve()),
        "outputs": str(outputs.resolve()),
        "rf_profiles": str(rf_profiles.resolve()),
        "captures": str(captures.resolve()),
        "normal_size": normal_size,
        "compact_target": [396, 112],
        "blocks_before_toggle": before,
        "blocks_after_toggle": after,
        "stream_continued": after > before,
        "note": "Rendu Qt offscreen automatisé ; inspection Windows native/DPI reste une preuve humaine séparée.",
    }
    (output / "ui-verification-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    bridge.stop(); window.spectrum.close(); window.hide(); bridge.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
