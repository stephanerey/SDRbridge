"""Minimal Soapy runtime probe used to qualify packaged Windows builds."""

from __future__ import annotations

import json
import ctypes  # Imported explicitly so PyInstaller sees shim dependencies.
import dataclasses
import pathlib
import typing

from sdr_bridge.app import create_source
from sdr_bridge.soapy_runtime import load_soapy_api


def main() -> int:
    soapy = load_soapy_api()
    source = create_source({"source": "soapy", "buffers": {"block_samples": 32768}})
    print(
        json.dumps(
            {
                "library": soapy.getLibVersion(),
                "api": soapy.getAPIVersion(),
                "abi": soapy.getABIVersion(),
                "modules": soapy.listModules(),
                "devices": soapy.Device_enumerate(),
                "app_devices": [item.to_dict() for item in source.enumerate()],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
