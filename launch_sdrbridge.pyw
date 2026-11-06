"""Visible, console-free launcher used by the Windows desktop shortcut."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from sdr_bridge.app import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main([
        "--source", "soapy",
        "--config", str(ROOT / "config.soapy-sdrpp.json"),
    ]))
