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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    bridge = SDRBridge(SimulatedSource(block_samples=4096), block_samples=4096)
    bridge.start()
    window = BridgeWindow(bridge); window.show(); QtTest.QTest.qWait(300)
    normal = output / "normal.png"; window.grab().save(str(normal))
    before = bridge.blocks_written; window.toggle_compact(); QtTest.QTest.qWait(200)
    compact = output / "compact.png"; window.grab().save(str(compact))
    after = bridge.blocks_written
    report = {
        "platform": os.environ.get("QT_QPA_PLATFORM"),
        "scale_factor": os.environ.get("QT_SCALE_FACTOR", "1"),
        "normal": str(normal.resolve()),
        "compact": str(compact.resolve()),
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
