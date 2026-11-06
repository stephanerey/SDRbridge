from __future__ import annotations

import argparse
from copy import deepcopy
import json
import logging
from pathlib import Path
import signal
import sys
import threading
import time

from .bridge import SDRBridge
from .config import DEFAULT_CONFIG, load_app_config, normalize_instance_name
from .control import ControlServer
from .iq_file import IQFileSource
from .model import RadioConfig, SampleFormat
from .logging_setup import configure_logging
from .native_control import NativeControlServer
from .native_sdrplay import NativeSDRplaySource
from .operations import WatchdogService
from .recording import ReplaySource, SigMFRecorder
from .soapy_source import SoapySource
from .source import SimulatedSource
from .udp import ProfileUDPStreamer
from . import __version__


logger = logging.getLogger(__name__)


class WindowSafeArgumentParser(argparse.ArgumentParser):
    """Argparse variant that also works in the windowed PyInstaller build."""

    def _print_message(self, message, file=None):
        stream = file or sys.stdout or sys.stderr
        if message and stream is not None:
            stream.write(message)


def _console_message(message: str, *, flush: bool = False) -> None:
    if sys.stdout is not None:
        print(message, flush=flush)


def _offset_endpoint(spec: str, offset: int) -> str:
    host, raw_port = str(spec).rsplit(":", 1)
    port = int(raw_port) + int(offset)
    if not host or not 1024 <= port <= 65535:
        raise ValueError(f"port offset produces an invalid endpoint: {spec}")
    return f"{host}:{port}"


def _offset_udp_entry(entry, offset: int):
    if isinstance(entry, str):
        return _offset_endpoint(entry, offset)
    if isinstance(entry, dict) and "endpoint" in entry:
        return {**entry, "endpoint": _offset_endpoint(entry["endpoint"], offset)}
    raise ValueError("UDP destination must be HOST:PORT or {endpoint, transport}")


def _normalize_udp_entries(
    entries,
    default_transport: str,
    default_rate: int | None = None,
    default_datagram_bytes: int | None = None,
    default_queue_blocks: int = 32,
) -> list[dict]:
    if entries is None:
        return []
    if isinstance(entries, (str, dict)):
        entries = [entries]
    normalized: list[dict] = []
    valid = {"sdbu_v2", "sdrpp_raw_cs16", "qmap_linrad"}
    allowed = {"endpoint", "transport", "sample_rate_sps", "datagram_bytes", "queue_blocks"}
    for entry in entries:
        if isinstance(entry, str):
            values = {"endpoint": entry, "transport": default_transport}
        elif isinstance(entry, dict) and "endpoint" in entry and not (set(entry) - allowed):
            values = dict(entry)
            values.setdefault("transport", default_transport)
        else:
            raise ValueError("UDP destination must be HOST:PORT or {endpoint, transport}")
        endpoint, transport = values["endpoint"], values["transport"]
        if not isinstance(endpoint, str) or transport not in valid:
            raise ValueError("invalid UDP endpoint or transport")
        rate = values.get("sample_rate_sps", default_rate)
        datagram_bytes = values.get("datagram_bytes", default_datagram_bytes)
        queue_blocks = values.get("queue_blocks", default_queue_blocks)
        if rate is not None and not 1 <= int(rate) <= 20_000_000:
            raise ValueError("UDP sample rate must be between 1 and 20000000 S/s")
        if datagram_bytes is not None and not 256 <= int(datagram_bytes) <= 65_507:
            raise ValueError("UDP datagram size must be between 256 and 65507 bytes")
        if not 4 <= int(queue_blocks) <= 4096:
            raise ValueError("UDP queue must contain between 4 and 4096 blocks")
        normalized.append({
            "endpoint": endpoint,
            "transport": transport,
            "sample_rate_sps": int(rate) if rate is not None else None,
            "datagram_bytes": int(datagram_bytes) if datagram_bytes is not None else None,
            "queue_blocks": int(queue_blocks),
        })
    return normalized


def build_parser() -> argparse.ArgumentParser:
    parser = WindowSafeArgumentParser(description=f"SDRbridge {__version__} — réception IQ multi-clients")
    parser.add_argument("--version", action="version", version=f"SDRbridge {__version__}")
    parser.add_argument("--list-devices", action="store_true", help="énumérer les récepteurs de la source sélectionnée puis quitter")
    parser.add_argument("--config", metavar="PATH", help="fichier app.json ou dossier de configuration")
    parser.add_argument("--instance", default="default", metavar="NAME", help="nom d'instance isolant configuration et journaux")
    parser.add_argument("--port-offset", type=int, default=0, metavar="N", help="décalage des ports contrôle et UDP pour une instance supplémentaire")
    parser.add_argument("--headless", action="store_true", help="fonctionner sans Qt")
    parser.add_argument("--source", choices=("simulated", "soapy", "native", "replay", "file", "sdrplay"))
    parser.add_argument("--replay", metavar="SIGMF_META")
    parser.add_argument("--iq-file", metavar="IQ_WAV", help="fichier IQ WAV/RF64 produit par HDSDR ou SDR++")
    parser.add_argument("--iq-center-frequency", type=int, metavar="HZ", help="fréquence centrale si elle est absente du nom du fichier IQ")
    parser.add_argument("--iq-loop", action=argparse.BooleanOptionalAction, default=None, help="boucler la lecture du fichier IQ")
    parser.add_argument("--device-id", metavar="ID", help="identifiant exact du SDR à ouvrir")
    parser.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    parser.add_argument("--log-dir", metavar="PATH", help="dossier des journaux persistants")
    parser.add_argument("--control-port", type=int, help="port historique loopback")
    parser.add_argument("--native-control-port", type=int, help="port natif JSON v1")
    parser.add_argument("--enable-network", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--auto-start", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--udp", metavar="HOST:PORT", action="append", help="destination opérateur UDP (répétable)")
    parser.add_argument("--udp-transport", choices=("sdbu_v2", "sdrpp_raw_cs16", "qmap_linrad"), default=None, help="format UDP opérateur")
    parser.add_argument("--udp-rate", type=int, metavar="SPS", help="taux de sortie des destinations --udp")
    parser.add_argument("--udp-datagram-bytes", type=int, metavar="BYTES", help="taille maximale des datagrammes des destinations --udp")
    parser.add_argument("--udp-queue-blocks", type=int, metavar="N", help="profondeur de file des destinations --udp")
    parser.add_argument("--frequency", type=int)
    parser.add_argument("--gain-reduction", type=int)
    parser.add_argument("--block-samples", type=int)
    return parser


def merged_config(args: argparse.Namespace) -> tuple[Path, dict]:
    instance_name = normalize_instance_name(args.instance)
    if args.port_offset < 0:
        raise ValueError("--port-offset must be zero or positive")
    path, loaded = load_app_config(args.config, instance_name=instance_name)
    config = deepcopy(loaded)
    if args.source:
        config["source"] = "native" if args.source == "sdrplay" else args.source
    if args.replay:
        config["source"] = "replay"; config["replay_path"] = args.replay
    config.setdefault("iq_file", {"path": None, "center_frequency_hz": None, "loop": False})
    if args.iq_file:
        config["source"] = "file"; config["iq_file"]["path"] = args.iq_file
    if args.iq_center_frequency is not None:
        config["iq_file"]["center_frequency_hz"] = args.iq_center_frequency
    if args.iq_loop is not None:
        config["iq_file"]["loop"] = args.iq_loop
    if args.device_id:
        config["device_id"] = args.device_id
    if args.log_level:
        config["log_level"] = args.log_level
    if args.control_port is not None:
        config["network"]["legacy_control_port"] = args.control_port
    if args.native_control_port is not None:
        config["network"]["control_port"] = args.native_control_port
    if args.enable_network is not None:
        config["network"]["enabled"] = args.enable_network
    if args.auto_start is not None:
        config["auto_start"] = args.auto_start
    if args.frequency is not None:
        config["radio"]["center_frequency_hz"] = args.frequency
    if args.gain_reduction is not None:
        config["radio"]["gain_reduction_db"] = args.gain_reduction
    if args.block_samples is not None:
        config["buffers"]["block_samples"] = args.block_samples
    if args.port_offset:
        for key in ("legacy_control_port", "control_port"):
            port = int(config["network"][key]) + args.port_offset
            if not 0 <= port <= 65535:
                raise ValueError(f"--port-offset produces an invalid {key}")
            config["network"][key] = port
        if config.get("udp_destination"):
            config["udp_destination"] = _offset_endpoint(config["udp_destination"], args.port_offset)
        config["udp_destinations"] = [
            _offset_udp_entry(item, args.port_offset) for item in config.get("udp_destinations", [])
        ]
    if config["source"] == "replay" and not config.get("replay_path"):
        raise ValueError("--source replay requires --replay or replay_path in configuration")
    if config["source"] == "file" and not config.get("iq_file", {}).get("path"):
        raise ValueError("--source file requires --iq-file or iq_file.path in configuration")
    return path, config


def create_source(config: dict):
    """Create the configured RX backend without opening any receiver."""
    source_kind = config["source"]
    block_samples = int(config["buffers"]["block_samples"])
    if source_kind == "simulated":
        return SimulatedSource(block_samples=block_samples)
    if source_kind == "soapy":
        return SoapySource(block_samples=block_samples)
    if source_kind == "native":
        return NativeSDRplaySource(block_samples=block_samples)
    if source_kind == "replay":
        return ReplaySource(config["replay_path"], block_samples=block_samples)
    if source_kind == "file":
        options = config.get("iq_file", {})
        return IQFileSource(
            options["path"],
            block_samples=block_samples,
            center_frequency_hz=options.get("center_frequency_hz"),
            loop=bool(options.get("loop", False)),
        )
    raise ValueError(f"unknown source: {source_kind}")


class AppRuntime:
    def __init__(
        self,
        config: dict,
        *,
        operator_udp=None,
        operator_udp_transport: str = "sdbu_v2",
        operator_udp_rate: int | None = None,
        operator_udp_datagram_bytes: int | None = None,
        operator_udp_queue_blocks: int = 32,
        run_id: str | None = None,
        instance_name: str = "default",
    ):
        self.config = config
        self.instance_name = normalize_instance_name(instance_name)
        buffers = config["buffers"]
        block_samples = int(buffers["block_samples"])
        source_kind = config["source"]
        source = create_source(config)
        self._hardware_source = source if source_kind in {"soapy", "native", "simulated"} else None
        self._hardware_source_kind = source_kind if self._hardware_source is not None else None
        self._hardware_config: RadioConfig | None = None
        radio = config["radio"]
        effective_format = SampleFormat.CS16
        if source_kind in {"replay", "file"}:
            source.open(source.device_id)
            file_config = source.configure(RadioConfig())
            effective_format = file_config.sample_format
            radio = {
                **radio,
                "center_frequency_hz": file_config.center_frequency_hz,
                "sample_rate_sps": file_config.sample_rate_sps,
                "bandwidth_hz": file_config.bandwidth_hz,
            }
        bridge_config = RadioConfig(
            center_frequency_hz=int(radio["center_frequency_hz"]),
            sample_rate_sps=int(radio["sample_rate_sps"]),
            bandwidth_hz=int(radio["bandwidth_hz"]),
            gain_reduction_db=int(radio["gain_reduction_db"]),
            agc_enabled=bool(radio["agc_enabled"]),
            antenna=radio.get("antenna"),
            gains=radio.get("gains", {}),
            sample_format=effective_format,
        )
        self.bridge = SDRBridge(
            source,
            bridge_config,
            block_samples=block_samples,
            slots=int(buffers["ring_slots"]),
            source_queue_blocks=int(buffers.get("source_queue_blocks", 256)),
            max_clients=buffers.get("max_clients"),
            device_id=(source.device_id if source_kind in {"replay", "file"} else config.get("device_id")),
            run_id=run_id,
        )
        if self._hardware_source is not None:
            self._hardware_config = bridge_config
        network = config["network"]
        self.legacy_control = ControlServer(self.bridge, port=int(network["legacy_control_port"]))
        self.native_control: NativeControlServer | None = None
        if network["enabled"]:
            token = None
            token_path = network.get("token_file")
            if token_path:
                token = Path(token_path).read_text(encoding="utf-8").strip()
            host = str(network["host"])
            self.native_control = NativeControlServer(
                self.bridge, host, int(network["control_port"]), token=token,
                allow_lan=host not in {"127.0.0.1", "localhost", "::1"},
            )
        if operator_udp is None:
            configured = config.get("udp_destinations")
            if configured is None or (configured == [] and config.get("udp_destination")):
                configured = config.get("udp_destination")
            operator_udp = configured
        self.operator_udp_transport = operator_udp_transport
        self.operator_udp_specs = _normalize_udp_entries(
            operator_udp,
            operator_udp_transport,
            operator_udp_rate,
            operator_udp_datagram_bytes,
            operator_udp_queue_blocks,
        )
        self.operator_udps: dict[str, ProfileUDPStreamer] = {}
        # Compatibility alias for older GUI/automation code. It points to the
        # first configured destination, while operator_udps contains all of
        # them.
        self.operator_udp: ProfileUDPStreamer | None = None
        self.watchdog = WatchdogService(self.bridge)
        self.recorder: SigMFRecorder | None = None
        self._recorder_token: str | None = None
        self._closed = False
        self.log_path: Path | None = None

    def available_sources(self) -> list[dict]:
        """Return switchable hardware devices plus the active file source."""
        devices: list[dict] = []
        if self._hardware_source is not None:
            devices.extend(item.to_dict() for item in self._hardware_source.enumerate())
        if isinstance(self.bridge.source, IQFileSource):
            devices.extend(item.to_dict() for item in self.bridge.source.enumerate())
        seen: set[str] = set()
        unique: list[dict] = []
        for item in devices:
            if item["device_id"] not in seen:
                seen.add(item["device_id"])
                unique.append(item)
        return unique

    @property
    def iq_file_path(self) -> Path | None:
        source = self.bridge.source
        return source.path if isinstance(source, IQFileSource) else None

    def select_iq_file(self, path: str, *, loop: bool = False) -> dict:
        """Replace the current SDR by a WAV/RF64 IQ source."""
        if self._hardware_source is self.bridge.source:
            self._hardware_config = self.bridge.config
        source = IQFileSource(
            path,
            block_samples=self.bridge.ring.block_samples,
            loop=loop,
        )
        effective = self.bridge.replace_source(source, source.device_id)
        if not self.bridge.running:
            self.bridge.start()
        self.config["source"] = "file"
        self.config["iq_file"] = {
            "path": str(Path(path)),
            "center_frequency_hz": None,
            "loop": bool(loop),
        }
        return effective.to_dict()

    def select_source_device(self, device_id: str) -> dict:
        """Select a hardware device, including when returning from a file."""
        if self._hardware_source is None:
            raise RuntimeError("no hardware backend is available in this session")
        if self.bridge.source is self._hardware_source:
            self.bridge.select_device(device_id)
            effective = self.bridge.config
        else:
            effective = self.bridge.replace_source(
                self._hardware_source,
                device_id,
                self._hardware_config,
            )
        self.config["source"] = self._hardware_source_kind
        self.config["device_id"] = device_id
        return effective.to_dict()

    def set_iq_file_loop(self, enabled: bool) -> None:
        source = self.bridge.source
        if not isinstance(source, IQFileSource):
            return
        source.loop = bool(enabled)
        self.config.setdefault("iq_file", {})["loop"] = bool(enabled)

    def start(self, *, start_rx: bool) -> None:
        logger.info(
            "runtime start requested",
            extra={"code": "RUNTIME_START", "run_id": self.bridge.run_id, "source_id": self.bridge.source_id, "details": {"source": self.config["source"], "start_rx": start_rx}},
        )
        self.legacy_control.start()
        if self.native_control:
            self.native_control.start()
        if start_rx:
            self.bridge.start()
        for entry in self.operator_udp_specs:
            self.add_udp_destination(**entry)
        self.watchdog.start()
        logger.info(
            "runtime started",
            extra={"code": "RUNTIME_READY", "run_id": self.bridge.run_id, "source_id": self.bridge.source_id, "epoch": str(self.bridge.epoch)},
        )

    @staticmethod
    def _parse_udp_destination(spec: str) -> tuple[str, int]:
        try:
            host, raw_port = str(spec).rsplit(":", 1)
            port = int(raw_port)
        except (TypeError, ValueError) as exc:
            raise ValueError("UDP destination must be HOST:PORT") from exc
        if not host or not 1024 <= port <= 65535:
            raise ValueError("UDP destination port must be between 1024 and 65535")
        return host, port

    def _build_udp_streamer(
        self,
        spec: str,
        transport: str | None = None,
        sample_rate_sps: int | None = None,
        datagram_bytes: int | None = None,
        queue_blocks: int = 32,
    ) -> tuple[str, ProfileUDPStreamer]:
        """Start one independent operator UDP destination and return metrics."""
        host, port = self._parse_udp_destination(spec)
        if host not in {"127.0.0.1", "localhost", "::1"} and not self.config["network"]["enabled"]:
            raise ValueError("LAN UDP requires network.enabled and explicit interface policy")
        selected_transport = transport or self.operator_udp_transport
        if selected_transport == "qmap_linrad":
            if sample_rate_sps not in {None, 96_000}:
                raise ValueError("QMAP/Linrad rate is fixed at 96000 S/s")
            sample_rate_sps = 96_000
        elif sample_rate_sps is None:
            sample_rate_sps = self.bridge.config.sample_rate_sps
        if not 1 <= int(sample_rate_sps) <= self.bridge.config.sample_rate_sps:
            raise ValueError(f"output rate must be between 1 and {self.bridge.config.sample_rate_sps} S/s")
        key = f"{host}:{port}"
        streamer = ProfileUDPStreamer(
            self.bridge,
            (host, port),
            transport=selected_transport,
            sample_rate_sps=int(sample_rate_sps),
            datagram_bytes=datagram_bytes,
            queue_blocks=queue_blocks,
        )
        return key, streamer

    def add_udp_destination(
        self,
        endpoint: str | None = None,
        transport: str | None = None,
        sample_rate_sps: int | None = None,
        datagram_bytes: int | None = None,
        queue_blocks: int = 32,
        *,
        spec: str | None = None,
    ) -> dict:
        spec = endpoint or spec
        key, streamer = self._build_udp_streamer(spec, transport, sample_rate_sps, datagram_bytes, queue_blocks)
        if key in self.operator_udps:
            raise ValueError(f"UDP destination already exists: {key}")
        self.operator_udps[key] = streamer
        try:
            streamer.start()
        except Exception:
            self.operator_udps.pop(key, None)
            raise
        if self.operator_udp is None:
            self.operator_udp = streamer
        return streamer.snapshot()

    def update_udp_destination(
        self,
        spec: str,
        transport: str,
        sample_rate_sps: int,
        datagram_bytes: int | None = None,
        queue_blocks: int = 32,
    ) -> dict:
        key, replacement = self._build_udp_streamer(spec, transport, sample_rate_sps, datagram_bytes, queue_blocks)
        previous = self.operator_udps.get(key)
        if previous is None:
            raise ValueError(f"UDP destination does not exist: {key}")
        replacement.start()
        self.operator_udps[key] = replacement
        if self.operator_udp is previous:
            self.operator_udp = replacement
        previous.stop()
        return replacement.snapshot()

    def remove_udp_destination(self, spec: str) -> None:
        host, port = self._parse_udp_destination(spec)
        key = f"{host}:{port}"
        streamer = self.operator_udps.pop(key, None)
        if streamer is None:
            return
        streamer.stop()
        self.operator_udp = next(iter(self.operator_udps.values()), None)

    def udp_destinations_snapshot(self) -> list[dict]:
        return [streamer.snapshot() for streamer in self.operator_udps.values()]

    def start_recording(self, base_path: str, profile_id: str, revision: int = 1) -> None:
        if self.recorder is not None:
            raise RuntimeError("a capture is already active")
        if not self.bridge.running:
            raise RuntimeError("start RX before recording")
        profile = self.bridge.profiles.get(profile_id, revision)
        profile.validate(self.bridge.config.sample_rate_sps)
        recorder = SigMFRecorder(base_path, profile.output_rate_sps, profile.sample_format, self.bridge.config.center_frequency_hz)
        recorder.start()
        try:
            token, _ = self.bridge.subscribe_profile(profile_id, revision, recorder.enqueue)
        except Exception:
            recorder.stop("activation du profil impossible")
            raise
        self.recorder = recorder
        self._recorder_token = token

    def stop_recording(self, reason: str = "arrêt demandé") -> None:
        recorder = self.recorder
        if recorder is None:
            return
        if self._recorder_token:
            self.bridge.unsubscribe_profile(self._recorder_token)
        recorder.stop(reason)
        self.recorder = None
        self._recorder_token = None

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        snapshot = self.bridge.status()
        logger.info(
            "runtime stop requested",
            extra={
                "code": "RUNTIME_STOP",
                "run_id": self.bridge.run_id,
                "source_id": self.bridge.source_id,
                "epoch": snapshot["epoch"],
                "details": {
                    "state": snapshot["state"],
                    "blocks_written": snapshot["blocks_written"],
                    "source_queue_drops": snapshot["source_queue_drops"],
                    "source_errors": snapshot["source_errors"],
                    "dispatch_processing_average_ms": snapshot["dispatch_processing_average_ms"],
                    "dispatch_processing_max_ms": snapshot["dispatch_processing_max_ms"],
                    "dispatch_slow_blocks": snapshot["dispatch_slow_blocks"],
                },
            },
        )
        try:
            self.stop_recording("arrêt application")
            self.watchdog.stop()
            for streamer in list(self.operator_udps.values()):
                streamer.stop()
            self.operator_udps.clear()
            self.operator_udp = None
            if self.native_control:
                self.native_control.close()
            self.legacy_control.close()
            self.bridge.close()
        except BaseException:
            logger.exception(
                "runtime shutdown failed",
                extra={"code": "RUNTIME_STOP_FAILED", "run_id": self.bridge.run_id, "source_id": self.bridge.source_id},
            )
            raise
        logger.info(
            "runtime stopped cleanly",
            extra={"code": "RUNTIME_STOPPED", "run_id": self.bridge.run_id, "source_id": self.bridge.source_id},
        )


def run_headless(runtime: AppRuntime) -> int:
    stopped = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    try:
        while not stopped.wait(2):
            _console_message(json.dumps(runtime.bridge.status(), ensure_ascii=False), flush=True)
            source = runtime.bridge.source
            if isinstance(source, (ReplaySource, IQFileSource)) and source.eof:
                runtime.bridge.stop()
                break
        return 0
    finally:
        runtime.close()


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit:
        raise
    try:
        instance_name = normalize_instance_name(args.instance)
    except ValueError as exc:
        _console_message(f"Configuration invalide: {exc}")
        return 2
    log_session = configure_logging("INFO", args.log_dir, instance_name=instance_name)
    runtime: AppRuntime | None = None
    exit_code = 0
    try:
        try:
            _, config = merged_config(args)
        except (ValueError, OSError) as exc:
            logger.error("configuration is invalid", exc_info=True, extra={"code": "CONFIG_INVALID"})
            _console_message(f"Configuration invalide: {exc}")
            exit_code = 2
            return exit_code
        log_session.set_level(config["log_level"])
        logger.info(
            "application starting",
            extra={
                "code": "APPLICATION_START",
                "details": {"headless": bool(args.headless), "source": config["source"], "instance": instance_name, "log_file": str(log_session.log_path) if log_session.log_path else None},
            },
        )
        if args.list_devices:
            source = None
            try:
                source = create_source(config)
                devices = [item.to_dict() for item in source.enumerate()]
                logger.info(
                    "device enumeration completed",
                    extra={"code": "DEVICE_ENUMERATION_READY", "details": {"devices": devices}},
                )
                _console_message(json.dumps(devices, ensure_ascii=False, indent=2))
                return 0
            except (ValueError, OSError, RuntimeError) as exc:
                logger.error("device enumeration failed", exc_info=True, extra={"code": "DEVICE_ENUMERATION_FAILED"})
                _console_message(f"Énumération impossible: {exc}")
                exit_code = 3
                return exit_code
            finally:
                if source is not None:
                    source.close()
        gui_application = None
        gui_runner = None
        if not args.headless:
            # PothosSDR ships another Qt build and prepends its bin directory
            # while loading Soapy. Initialize our bundled platform plugin first
            # so Windows cannot mix both Qt runtimes in the same process.
            from .gui import prepare_gui, run_gui

            gui_application = prepare_gui()
            gui_runner = run_gui
            logger.info(
                "bundled Qt runtime initialized before SDR backend",
                extra={"code": "GUI_RUNTIME_READY"},
            )
        try:
            configured_udp = args.udp if args.udp is not None else config.get("udp_destinations")
            if not configured_udp and config.get("udp_destination"):
                configured_udp = config.get("udp_destination")
            runtime = AppRuntime(
                config,
                operator_udp=configured_udp,
                operator_udp_transport=args.udp_transport or config.get("udp_transport", "sdbu_v2"),
                operator_udp_rate=args.udp_rate,
                operator_udp_datagram_bytes=args.udp_datagram_bytes,
                operator_udp_queue_blocks=(args.udp_queue_blocks if args.udp_queue_blocks is not None else 32),
                run_id=log_session.run_id,
                instance_name=instance_name,
            )
            runtime.log_path = log_session.log_path
            runtime.start(start_rx=bool(args.headless or config["auto_start"]))
        except (ValueError, OSError, RuntimeError) as exc:
            logger.error("application startup failed", exc_info=True, extra={"code": "STARTUP_FAILED"})
            if runtime:
                try:
                    runtime.close()
                except Exception:
                    logger.exception("cleanup after startup failure failed", extra={"code": "STARTUP_CLEANUP_FAILED"})
            _console_message(f"Démarrage impossible: {exc}")
            exit_code = 3
            return exit_code
        try:
            if args.headless:
                exit_code = run_headless(runtime)
            else:
                exit_code = gui_runner(runtime.bridge, runtime)
            return exit_code
        except KeyboardInterrupt:
            logger.info("application interrupted by user", extra={"code": "APPLICATION_INTERRUPTED"})
            exit_code = 0
            return exit_code
        except BaseException:
            logger.critical("fatal application error", exc_info=True, extra={"code": "APPLICATION_FATAL"})
            exit_code = 4
            return exit_code
        finally:
            if runtime and not runtime._closed:
                try:
                    runtime.close()
                except BaseException:
                    logger.exception("final runtime cleanup failed", extra={"code": "FINAL_CLEANUP_FAILED"})
    finally:
        logger.info("application process exiting", extra={"code": "APPLICATION_EXIT", "details": {"exit_code": exit_code}})
        log_session.close()


if __name__ == "__main__":
    raise SystemExit(main())
