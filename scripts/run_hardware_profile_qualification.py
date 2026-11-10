from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import time

from sdr_bridge.app import AppRuntime
from sdr_bridge.config import DEFAULT_CONFIG
from sdr_bridge.logging_setup import configure_logging


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Qualify a real SDR source with one high-rate UDP profile and optional QMAP output"
    )
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--source-rate", type=int, default=10_000_000)
    parser.add_argument("--bandwidth", type=int, default=8_000_000)
    parser.add_argument("--udp-rate", type=int, default=4_000_000)
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--with-qmap", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("output") / "hardware-profile")
    parser.add_argument("--soapy-root", type=Path)
    args = parser.parse_args()
    if args.duration <= 0:
        parser.error("--duration must be positive")

    project = Path(__file__).resolve().parents[1]
    private_soapy = args.soapy_root or project / "build-final" / "dependencies" / "soapy-runtime"
    if (private_soapy / "bin" / "SoapySDR.dll").is_file():
        os.environ["SDRBRIDGE_SOAPY_ROOT"] = str(private_soapy.resolve())

    args.output.mkdir(parents=True, exist_ok=True)
    session = configure_logging("INFO", args.output / "logs", instance_name="hardware-profile", stream=False)
    runtime: AppRuntime | None = None
    samples: list[dict] = []
    result: dict = {}
    try:
        config = deepcopy(DEFAULT_CONFIG)
        config["source"] = "soapy"
        config["device_id"] = args.device_id
        config["radio"].update(
            sample_rate_sps=args.source_rate,
            bandwidth_hz=args.bandwidth,
        )
        config["network"].update(legacy_control_port=0, control_port=0)
        config["udp_destinations"] = [
            {
                "endpoint": "127.0.0.1:17355",
                "transport": "sdbu_v2",
                "sample_rate_sps": args.udp_rate,
                "datagram_bytes": 8192,
                "queue_blocks": 64,
            }
        ]
        if args.with_qmap:
            config["udp_destinations"].append(
                {"endpoint": "127.0.0.1:15004", "transport": "qmap_linrad"}
            )
        runtime = AppRuntime(config, run_id=session.run_id, instance_name="hardware-profile")
        runtime.log_path = session.log_path
        runtime.start(start_rx=True)
        deadline = time.monotonic() + args.duration
        while time.monotonic() < deadline:
            time.sleep(min(1.0, max(0.01, deadline - time.monotonic())))
            status = runtime.bridge.status()
            samples.append(
                {
                    "elapsed_s": round(args.duration - max(0.0, deadline - time.monotonic()), 3),
                    "sample_rate_measured": round(float(status["sample_rate_measured"]), 3),
                    "source_losses": status["source_losses"],
                    "source_queue_drops": status["source_queue_drops"],
                    "dsp_queue_drops": status["dsp_queue_drops"],
                    "profile_queue_drops": status["profile_queue_drops"],
                    "pipelines": status["pipelines"],
                }
            )
        final = runtime.bridge.status()
        result = {
            "ok": (
                final["sample_rate_measured"] >= args.source_rate * 0.9
                and final["source_queue_drops"] == 0
                and final["dsp_queue_drops"] == 0
                and final["profile_queue_drops"] == 0
                and final["source_errors"] == 0
            ),
            "requested_source_rate": args.source_rate,
            "requested_udp_rate": args.udp_rate,
            "qmap_enabled": args.with_qmap,
            "final": final,
            "samples": samples,
            "log_file": str(session.log_path) if session.log_path else None,
        }
    except BaseException as exc:
        result = {"ok": False, "error": str(exc), "samples": samples}
    finally:
        if runtime is not None:
            try:
                runtime.close()
            except BaseException as exc:
                result["shutdown_error"] = str(exc)
                result["ok"] = False
        session.close()

    report_path = args.output / "report.json"
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "ok": result.get("ok", False),
        "sample_rate_measured": result.get("final", {}).get("sample_rate_measured"),
        "source_losses": result.get("final", {}).get("source_losses"),
        "source_queue_drops": result.get("final", {}).get("source_queue_drops"),
        "dsp_queue_drops": result.get("final", {}).get("dsp_queue_drops"),
        "profile_queue_drops": result.get("final", {}).get("profile_queue_drops"),
        "report": str(report_path.resolve()),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
