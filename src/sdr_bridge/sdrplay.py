from __future__ import annotations

import ctypes
from pathlib import Path

from .model import RadioConfig
from .source import BlockCallback, IQSource


class SDRplaySource(IQSource):
    """Boundary for the official SDRplay API.

    The SDK callback ABI varies by API release. This class deliberately refuses
    to stream until an approved SDK adapter for the installed API version is
    selected. It does perform safe DLL discovery/version probing.
    """

    DLL_NAMES = ("sdrplay_api.dll", "sdrplay_api64.dll")

    def __init__(self, dll_path: str | None = None):
        self._dll_path = Path(dll_path) if dll_path else self._discover()
        self._dll: ctypes.WinDLL | None = None

    @property
    def name(self) -> str:
        return "SDRplay RSP1A"

    @classmethod
    def _discover(cls) -> Path | None:
        roots = [
            Path(r"C:\Program Files\SDRplay\API\x64"),
            Path(r"C:\Program Files\SDRplay\API"),
        ]
        for root in roots:
            for name in cls.DLL_NAMES:
                candidate = root / name
                if candidate.exists():
                    return candidate
        return None

    def available(self) -> bool:
        return self._dll_path is not None

    def start(self, config: RadioConfig, callback: BlockCallback) -> None:
        config.validate()
        if not self._dll_path:
            raise RuntimeError("SDRplay API DLL not found; install the official SDRplay API")
        self._dll = ctypes.WinDLL(str(self._dll_path))
        raise RuntimeError(
            "SDRplay DLL found, but the version-specific callback adapter is not enabled. "
            "Run with --source simulated until the approved SDK headers are integrated."
        )

    def stop(self) -> None:
        self._dll = None

    def apply_config(self, config: RadioConfig) -> None:
        config.validate()
        if self._dll is None:
            raise RuntimeError("SDRplay source is not active")

