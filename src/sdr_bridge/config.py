from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any
import re

import jsonschema


DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": 1,
    "source": "simulated",
    "device_id": None,
    "replay_path": None,
    "radio": {
        "center_frequency_hz": 144_300_000,
        "sample_rate_sps": 2_000_000,
        "bandwidth_hz": 1_536_000,
        "gain_reduction_db": 40,
        "agc_enabled": False,
        "antenna": None,
        "gains": {},
    },
    "network": {
        "enabled": False,
        "host": "127.0.0.1",
        "control_port": 47_632,
        "legacy_control_port": 47_631,
        "token_file": None,
        "mdns": False,
    },
    "buffers": {"ring_slots": 64, "block_samples": 4096, "source_queue_blocks": 256, "max_clients": None},
    "auto_connect": False,
    "auto_start": False,
    "udp_destination": None,
    "udp_destinations": [],
    "udp_transport": "sdbu_v2",
    "log_level": "INFO",
}


INSTANCE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def normalize_instance_name(value: str | None) -> str:
    name = (value or "default").strip()
    if not INSTANCE_NAME_PATTERN.fullmatch(name):
        raise ValueError("instance name must contain 1-64 letters, digits, '.', '_' or '-'")
    return name


def default_config_root(instance_name: str | None = None) -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        raise RuntimeError("LOCALAPPDATA is unavailable")
    root = Path(base) / "SDRbridge"
    instance = normalize_instance_name(instance_name)
    return root if instance == "default" else root / "instances" / instance


def schema_path(name: str) -> Path:
    roots = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        roots.append(Path(sys._MEIPASS))  # type: ignore[attr-defined]
    roots.extend((Path(__file__).resolve().parents[2], Path(__file__).resolve().parent.parent))
    for root in roots:
        candidate = root / "schemas" / name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"schema SDRbridge introuvable: {name}")


def _load_schema(name: str) -> dict:
    return json.loads(schema_path(name).read_text(encoding="utf-8"))


def validate_document(value: dict, schema_name: str) -> None:
    validator = jsonschema.Draft202012Validator(_load_schema(schema_name))
    errors = sorted(validator.iter_errors(value), key=lambda item: list(item.path))
    if errors:
        first = errors[0]
        location = ".".join(map(str, first.path)) or "$"
        raise ValueError(f"invalid {schema_name} at {location}: {first.message}")


def read_json(path: Path, schema_name: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except Exception as exc:
        raise ValueError(f"invalid JSON file {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    validate_document(value, schema_name)
    return value


def atomic_write_json(path: Path, value: dict, schema_name: str) -> None:
    validate_document(value, schema_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def load_app_config(root_or_file: str | Path | None = None, *, instance_name: str | None = None) -> tuple[Path, dict]:
    target = Path(root_or_file) if root_or_file else default_config_root(instance_name)
    path = target if target.suffix.lower() == ".json" else target / "app.json"
    if not path.exists():
        return path, deepcopy(DEFAULT_CONFIG)
    return path, read_json(path, "app.schema.json")


def save_app_config(path: Path, value: dict) -> None:
    atomic_write_json(path, value, "app.schema.json")


def save_preset(path: Path, value: dict) -> None:
    atomic_write_json(path, value, "preset.schema.json")


def load_preset(path: Path) -> dict:
    return read_json(path, "preset.schema.json")


def save_window(path: Path, value: dict) -> None:
    atomic_write_json(path, value, "window.schema.json")


def load_window(path: Path) -> dict:
    return read_json(path, "window.schema.json")
