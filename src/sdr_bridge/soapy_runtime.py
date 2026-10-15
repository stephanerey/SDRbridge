from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType


def _compatibility_module_candidates() -> tuple[Path, ...]:
    candidates: list[Path] = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / "soapy_compat" / "SoapySDR.py")  # type: ignore[attr-defined]
    candidates.append(Path(__file__).resolve().parents[2] / "soapy_sdr_ctypes_compat" / "SoapySDR.py")
    return tuple(candidates)


def load_soapy_api() -> ModuleType:
    """Load official bindings when present, otherwise the bundled ctypes shim."""
    try:
        import SoapySDR

        return SoapySDR
    except ImportError as original:
        for candidate in _compatibility_module_candidates():
            if not candidate.is_file():
                continue
            spec = importlib.util.spec_from_file_location("sdrbridge_soapy_compat", candidate)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            try:
                spec.loader.exec_module(module)
            except BaseException:
                sys.modules.pop(spec.name, None)
                raise
            return module
        raise RuntimeError(
            "SoapySDR is unavailable; install PothosSDR or the SoapySDR Python bindings"
        ) from original
