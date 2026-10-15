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
from .model import RadioConfig, SampleFormat
from .logging_setup import configure_logging
from .native_control import NativeControlServer
from .native_sdrplay import NativeSDRplaySource
from .operations import WatchdogService
from .recording import ReplaySource, SigMFRecorder
from .soapy_source import SoapySource
from .source import SimulatedSource
from .udp import UDPStreamer
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


def build_parser() -> argparse.ArgumentParser:
    parser = WindowSafeArgumentParser(description=f"SDRbridge {__version__} — réception IQ multi-clients")
    parser.add_argument("--version", action="version", version=f"SDRbridge {__version__}")
    parser.add_argument("--list-devices", action="store_true", help="énumérer les récepteurs de la source sélectionnée puis quitter")
    parser.add_argument("--config", metavar="PATH", help="fichier app.json ou dossier de configuration")
    parser.add_argument("--instance", default="default", metavar="NAME", help="nom d'instance isolant configuration et journaux")
    parser.add_argument("--port-offset", type=int, default=0, metavar="N", help="décalage des ports contrôle et UDP pour une instance supplémentaire")
    parser.add_argument("--headless", action="store_true", help="fonctionner sans Qt")
    parser.add_argument("--source", choices=("simulated", "soapy", "native", "replay", "sdrplay"))
    parser.add_argument("--replay", metavar="SIGMF_META")
    parser.add_argument("--device-id", metavar="ID", help="identifiant exact du SDR à ouvrir")
    parser.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    parser.add_argument("--log-dir", metavar="PATH", help="dossier des journaux persistants")
    parser.add_argument("--control-port", type=int, help="port historique loopback")
    parser.add_argument("--native-control-port", type=int, help="port natif JSON v1")
    parser.add_argument("--enable-network", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--auto-start", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--udp", metavar="HOST:PORT", action="append", help="destination opérateur UDP (répétable)")
    parser.add_argument("--udp-transport", choices=("sdbu_v2", "sdrpp_raw_cs16"), default=None, help="format UDP opérateur")
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
            _offset_endpoint(item, args.port_offset) for item in config.get("udp_destinations", [])
        ]
    if config["source"] == "replay" and not config.get("replay_path"):
        raise ValueError("--source replay requires --replay or replay_path in configuration")
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
        return NativeSDRplaySource()
    if source_kind == "replay":
        return ReplaySource(config["replay_path"], block_samples=block_samples)
    raise ValueError(f"unknown source: {source_kind}")


class AppRuntime:
    def __init__(self, config: dict, *, operator_udp: str | list[str] | None = None, operator_udp_transport: str = "sdbu_v2", run_id: str | None = None, instance_name: str = "default"):
        self.config = config
        self.instance_name = normalize_instance_name(instance_name)
        buffers = config["buffers"]
        block_samples = int(buffers["block_samples"])
        source_kind = config["source"]
        source = create_source(config)
        radio = config["radio"]
        effective_format = SampleFormat.CS16
        if source_kind == "replay":
            source.open(source.device_id)
            replay_config = source.configure(RadioConfig())
            effective_format = replay_config.sample_format
            radio = {
                **radio,
                "center_frequency_hz": replay_config.center_frequency_hz,
                "sample_rate_sps": replay_config.sample_rate_sps,
                "bandwidth_hz": replay_config.bandwidth_hz,
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
            device_id=config.get("device_id"),
            run_id=run_id,
        )
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
        if isinstance(operator_udp, str):
            operator_udp = [operator_udp]
        self.operator_udp_specs = list(operator_udp or [])
        self.operator_udp_transport = operator_udp_transport
        self.operator_udps: dict[str, UDPStreamer] = {}
        # Compatibility alias for older GUI/automation code. It points to the
        # first configured destination, while operator_udps contains all of
        # them.
        self.operator_udp: UDPStreamer | None = None
        self.watchdog = WatchdogService(self.bridge)
        self.recorder: SigMFRecorder | None = None
        self._recorder_token: str | None = None
        self._closed = False
        self.log_path: Path | None = None

    def start(self, *, start_rx: bool) -> None:
        logger.info(
            "runtime start requested",
            extra={"code": "RUNTIME_START", "run_id": self.bridge.run_id, "source_id": self.bridge.source_id, "details": {"source": self.config["source"], "start_rx": start_rx}},
        )
        self.bridge.open()
        self.legacy_control.start()
        if self.native_control:
            self.native_control.start()
        if start_rx:
            self.bridge.start()
        for spec in self.operator_udp_specs:
            self.add_udp_destination(spec, self.operator_udp_transport)
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

    def add_udp_destination(self, spec: str, transport: str | None = None) -> dict:
        """Start one independent operator UDP destination and return metrics."""
        host, port = self._parse_udp_destination(spec)
        if host not in {"127.0.0.1", "localhost", "::1"} and not self.config["network"]["enabled"]:
            raise ValueError("LAN UDP requires network.enabled and explicit interface policy")
        key = f"{host}:{port}"
        if key in self.operator_udps:
            raise ValueError(f"UDP destination already exists: {key}")
        streamer = UDPStreamer(self.bridge.ring, (host, port), transport=transport or self.operator_udp_transport)
        self.operator_udps[key] = streamer
        try:
            streamer.start()
        except Exception:
            self.operator_udps.pop(key, None)
            raise
        if self.operator_udp is None:
            self.operator_udp = streamer
        return streamer.destination.snapshot()

    def remove_udp_destination(self, spec: str) -> None:
        host, port = self._parse_udp_destination(spec)
        key = f"{host}:{port}"
        streamer = self.operator_udps.pop(key, None)
        if streamer is None:
            return
        streamer.stop()
        self.operator_udp = next(iter(self.operator_udps.values()), None)

    def udp_destinations_snapshot(self) -> list[dict]:
        return [streamer.destination.snapshot() for streamer in self.operator_udps.values()]

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
            if isinstance(source, ReplaySource) and source.eof:
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
        try:
            configured_udp = args.udp if args.udp is not None else config.get("udp_destinations")
            if not configured_udp and config.get("udp_destination"):
                configured_udp = config.get("udp_destination")
            runtime = AppRuntime(
                config,
                operator_udp=configured_udp,
                operator_udp_transport=args.udp_transport or config.get("udp_transport", "sdbu_v2"),
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
                from .gui import run_gui
                exit_code = run_gui(runtime.bridge, runtime)
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
