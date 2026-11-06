from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5 import QtTest, QtWidgets

from sdr_bridge.bridge import SDRBridge
from sdr_bridge.gui import BridgeWindow
from sdr_bridge.source import SimulatedSource


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
    args = parser.parse_args()
    output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    bridge = SDRBridge(SimulatedSource(block_samples=4096), block_samples=4096)
    bridge.start()
    window = BridgeWindow(bridge, CaptureRuntime(bridge)); window.show(); QtTest.QTest.qWait(300)
    normal = output / "normal.png"; window.grab().save(str(normal))
    window.tabs.setCurrentIndex(1); QtTest.QTest.qWait(100)
    outputs = output / "outputs.png"; window.grab().save(str(outputs))
    window.tabs.setCurrentIndex(0)
    before = bridge.blocks_written; window.toggle_compact(); QtTest.QTest.qWait(200)
    compact = output / "compact.png"; window.grab().save(str(compact))
    after = bridge.blocks_written
    report = {
        "platform": os.environ.get("QT_QPA_PLATFORM"),
        "scale_factor": os.environ.get("QT_SCALE_FACTOR", "1"),
        "normal": str(normal.resolve()),
        "compact": str(compact.resolve()),
        "outputs": str(outputs.resolve()),
        "normal_size": [1100, 720],
        "compact_target": [480, 120],
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
