from __future__ import annotations

from datetime import datetime, timezone
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import re
import sys
import zipfile
from typing import Any


_PRIVATE_KEY_PARTS = ("token", "password", "passwd", "secret", "credential", "api_key")
_PACKAGE_NAMES = ("numpy", "scipy", "PyQt5", "pyqtgraph", "zeroconf", "PyYAML", "jsonschema")


def sanitize(value: Any) -> Any:
    """Return a JSON-safe copy with credentials and the user profile hidden."""
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for raw_key, item in value.items():
            key = str(raw_key)
            if any(part in key.lower() for part in _PRIVATE_KEY_PARTS):
                clean[key] = "<redacted>"
            else:
                clean[key] = sanitize(item)
        return clean
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if isinstance(value, Path):
        value = str(value)
    if isinstance(value, str):
        profile = os.environ.get("USERPROFILE")
        if profile:
            value = value.replace(profile, "<USERPROFILE>").replace(profile.replace("\\", "/"), "<USERPROFILE>")
        return value
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)


def _dependency_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for package in _PACKAGE_NAMES:
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = "not installed"
    return versions


def _soapy_versions() -> dict[str, str]:
    try:
        from .soapy_runtime import load_soapy_api

        api = load_soapy_api()
        return {
            "library": str(api.getLibVersion()) if hasattr(api, "getLibVersion") else "unknown",
            "api": str(api.getAPIVersion()) if hasattr(api, "getAPIVersion") else "unknown",
            "abi": str(api.getABIVersion()) if hasattr(api, "getABIVersion") else "unknown",
            "root": sanitize(
                os.environ.get("SDRBRIDGE_SOAPY_ROOT")
                or os.environ.get("SOAPY_SDR_ROOT", "unknown")
            ),
        }
    except BaseException as exc:
        return {"error": str(exc)}


def _sanitized_log_tail(path: Path, limit_bytes: int = 2_000_000) -> str:
    with path.open("rb") as handle:
        size = handle.seek(0, 2)
        handle.seek(max(0, size - limit_bytes))
        raw = handle.read()
    text = raw.decode("utf-8", errors="replace")
    if size > limit_bytes and "\n" in text:
        text = text.split("\n", 1)[1]
    profile = os.environ.get("USERPROFILE")
    if profile:
        text = text.replace(profile, "<USERPROFILE>").replace(profile.replace("\\", "/"), "<USERPROFILE>")
    text = re.sub(
        r'(?i)("?(?:token|password|passwd|secret|api_key)"?\s*[:=]\s*)"?[^",\s}]+',
        r'\1"<redacted>"',
        text,
    )
    return text


def export_diagnostic_bundle(
    destination: str | Path,
    *,
    app_version: str,
    diagnostics: dict[str, Any],
    configuration: dict[str, Any] | None = None,
    log_path: str | Path | None = None,
) -> Path:
    """Create a portable, sanitized ZIP suitable for a public bug report."""
    target = Path(destination)
    if target.suffix.lower() != ".zip":
        target = target.with_suffix(".zip")
    target.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "application": {"name": "SDRbridge", "version": app_version, "frozen": bool(getattr(sys, "frozen", False))},
        "system": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "architecture": platform.machine(),
            "logical_cpu_count": os.cpu_count(),
        },
        "dependencies": _dependency_versions(),
        "soapy": _soapy_versions(),
    }
    entries = {
        "report.json": report,
        "diagnostics.json": sanitize(diagnostics),
        "configuration.json": sanitize(configuration or {}),
    }
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, payload in entries.items():
            archive.writestr(name, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        if log_path:
            source = Path(log_path)
            if source.is_file():
                archive.writestr("logs/sdrbridge-recent.jsonl", _sanitized_log_tail(source))
            fault = source.with_name("sdrbridge-fault.log")
            if fault.is_file():
                archive.writestr("logs/sdrbridge-fault-recent.log", _sanitized_log_tail(fault))
        archive.writestr(
            "README.txt",
            "SDRbridge diagnostic bundle\n"
            "Credentials and the Windows user-profile path are redacted.\n"
            "Review this archive before publishing it because SDR model, serial number, "
            "frequencies and UDP endpoints can still be operationally sensitive.\n",
        )
    return target
