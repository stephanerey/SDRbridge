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
from .config import DEFAULT_CONFIG, load_app_config
from .control import ControlServer
from .model import RadioConfig, SampleFormat
from .native_control import NativeControlServer
from .native_sdrplay import NativeSDRplaySource
from .operations import WatchdogService
from .recording import ReplaySource, SigMFRecorder
from .soapy_source import SoapySource
from .source import SimulatedSource
from .udp import UDPStreamer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SDRbridge 0.3 — réception IQ multi-clients")
    parser.add_argument("--config", metavar="PATH", help="fichier app.json ou dossier de configuration")
    parser.add_argument("--headless", action="store_true", help="fonctionner sans Qt")
    parser.add_argument("--source", choices=("simulated", "soapy", "native", "replay", "sdrplay"))
    parser.add_argument("--replay", metavar="SIGMF_META")
    parser.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    parser.add_argument("--control-port", type=int, help="port historique loopback")
    parser.add_argument("--native-control-port", type=int, help="port natif JSON v1")
    parser.add_argument("--enable-network", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--auto-start", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--udp", metavar="HOST:PORT", help="destination opérateur UDP")
    parser.add_argument("--udp-transport", choices=("sdbu_v2", "sdrpp_raw_cs16"), default=None, help="format UDP opérateur")
    parser.add_argument("--frequency", type=int)
    parser.add_argument("--gain-reduction", type=int)
    parser.add_argument("--block-samples", type=int)
    return parser


def merged_config(args: argparse.Namespace) -> tuple[Path, dict]:
    path, loaded = load_app_config(args.config)
    config = deepcopy(loaded)
    if args.source:
        config["source"] = "native" if args.source == "sdrplay" else args.source
    if args.replay:
        config["source"] = "replay"; config["replay_path"] = args.replay
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
    if config["source"] == "replay" and not config.get("replay_path"):
        raise ValueError("--source replay requires --replay or replay_path in configuration")
    return path, config


class AppRuntime:
    def __init__(self, config: dict, *, operator_udp: str | None = None, operator_udp_transport: str = "sdbu_v2"):
        self.config = config
        buffers = config["buffers"]
        source_kind = config["source"]
        block_samples = int(buffers["block_samples"])
        if source_kind == "simulated":
            source = SimulatedSource(block_samples=block_samples)
        elif source_kind == "soapy":
            source = SoapySource(block_samples=block_samples)
        elif source_kind == "native":
            source = NativeSDRplaySource()
        elif source_kind == "replay":
            source = ReplaySource(config["replay_path"], block_samples=block_samples)
        else:
            raise ValueError(f"unknown source: {source_kind}")
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
        self.operator_udp_spec = operator_udp
        self.operator_udp_transport = operator_udp_transport
        self.operator_udp: UDPStreamer | None = None
        self.watchdog = WatchdogService(self.bridge)
        self.recorder: SigMFRecorder | None = None
        self._recorder_token: str | None = None
        self._closed = False

    def start(self, *, start_rx: bool) -> None:
        self.bridge.open()
        self.legacy_control.start()
        if self.native_control:
            self.native_control.start()
        if start_rx:
            self.bridge.start()
        if self.operator_udp_spec:
            host, raw_port = self.operator_udp_spec.rsplit(":", 1)
            if host not in {"127.0.0.1", "localhost"} and not self.config["network"]["enabled"]:
                raise ValueError("LAN UDP requires network.enabled and explicit interface policy")
            self.operator_udp = UDPStreamer(self.bridge.ring, (host, int(raw_port)), transport=self.operator_udp_transport)
            self.operator_udp.start()
        self.watchdog.start()

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
        self.stop_recording("arrêt application")
        self.watchdog.stop()
        if self.operator_udp:
            self.operator_udp.stop()
        if self.native_control:
            self.native_control.close()
        self.legacy_control.close()
        self.bridge.close()


def run_headless(runtime: AppRuntime) -> int:
    stopped = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    try:
        while not stopped.wait(2):
            print(json.dumps(runtime.bridge.status(), ensure_ascii=False), flush=True)
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
        _, config = merged_config(args)
    except (ValueError, OSError) as exc:
        print(f"Configuration invalide: {exc}")
        return 2
    logging.basicConfig(level=getattr(logging, config["log_level"]), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    runtime: AppRuntime | None = None
    try:
        runtime = AppRuntime(
            config,
            operator_udp=args.udp if args.udp is not None else config.get("udp_destination"),
            operator_udp_transport=args.udp_transport or config.get("udp_transport", "sdbu_v2"),
        )
        runtime.start(start_rx=bool(args.headless or config["auto_start"]))
    except (ValueError, OSError, RuntimeError) as exc:
        try:
            error_path = Path(sys.executable).resolve().parent / "sdrbridge-startup-error.log"
            error_path.write_text(f"Démarrage impossible: {exc}\n", encoding="utf-8")
        except Exception:
            pass
        if runtime:
            try:
                runtime.close()
            except Exception:
                pass
        print(f"Démarrage impossible: {exc}")
        return 3
    if args.headless:
        return run_headless(runtime)
    from .gui import run_gui
    return run_gui(runtime.bridge, runtime)


if __name__ == "__main__":
    raise SystemExit(main())
