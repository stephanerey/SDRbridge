from __future__ import annotations

import argparse
from copy import deepcopy
import json
import multiprocessing
from pathlib import Path
import queue
import re
import time
import traceback

from sdr_bridge.app import AppRuntime
from sdr_bridge.config import DEFAULT_CONFIG
from sdr_bridge.logging_setup import configure_logging


def _instance_name(device_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", device_id).strip("-")[-64:]


def _worker(device_id: str, duration_s: float, output_root: str, result_queue) -> None:
    instance = _instance_name(device_id)
    log_dir = Path(output_root) / instance / "logs"
    session = configure_logging("INFO", log_dir, instance_name=instance, stream=False)
    runtime = None
    started = time.monotonic()
    try:
        config = deepcopy(DEFAULT_CONFIG)
        config["source"] = "native" if device_id.startswith("native-sdrplay:") else "soapy"
        config["device_id"] = device_id
        config["network"] = deepcopy(DEFAULT_CONFIG["network"])
        config["network"]["legacy_control_port"] = 0
        config["network"]["control_port"] = 0
        config["udp_destination"] = None
        config["udp_destinations"] = []
        runtime = AppRuntime(config, run_id=session.run_id, instance_name=instance)
        runtime.log_path = session.log_path
        runtime.start(start_rx=True)
        deadline = time.monotonic() + duration_s
        while time.monotonic() < deadline:
            if runtime.bridge.state.value == "ERROR":
                raise RuntimeError(runtime.bridge.status().get("last_error") or "source entered ERROR")
            time.sleep(0.1)
        status = runtime.bridge.status()
        measured = float(status["sample_rate_measured"])
        requested = int(config["radio"]["sample_rate_sps"])
        rate_ok = measured >= requested * 0.8
        result_queue.put({
            "ok": rate_ok,
            "device_id": device_id,
            "duration_s": round(time.monotonic() - started, 3),
            "blocks_written": status["blocks_written"],
            "samples_written": status["samples_written"],
            "source_queue_drops": status["source_queue_drops"],
            "source_errors": status["source_errors"],
            "sample_rate_requested": requested,
            "sample_rate_measured": measured,
            "rate_ok": rate_ok,
            "error": None if rate_ok else f"measured sample rate below 80% of requested rate ({measured:.0f} < {requested * 0.8:.0f})",
            "log_file": str(session.log_path) if session.log_path else None,
        })
    except BaseException as exc:
        result_queue.put({
            "ok": False,
            "device_id": device_id,
            "duration_s": round(time.monotonic() - started, 3),
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "log_file": str(session.log_path) if session.log_path else None,
        })
    finally:
        if runtime is not None:
            try:
                runtime.close()
            except BaseException:
                pass
        session.close()


def _run_group(device_ids: list[str], duration_s: float, output_root: Path) -> list[dict]:
    context = multiprocessing.get_context("spawn")
    result_queue = context.Queue()
    processes = [
        context.Process(target=_worker, args=(device_id, duration_s, str(output_root), result_queue))
        for device_id in device_ids
    ]
    for process in processes:
        process.start()
    timeout = duration_s + 20.0
    for process in processes:
        process.join(timeout)
    results: list[dict] = []
    while True:
        try:
            results.append(result_queue.get_nowait())
        except queue.Empty:
            break
    reported = {item["device_id"] for item in results}
    for device_id, process in zip(device_ids, processes):
        if process.is_alive():
            process.terminate()
            process.join(5)
        if device_id not in reported:
            results.append({
                "ok": False,
                "device_id": device_id,
                "error": f"worker exited without a result (exit code {process.exitcode})",
            })
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded RX-only hardware smoke for one or more SoapySDR devices")
    parser.add_argument("--device-id", action="append", required=True)
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--simultaneous", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("output") / "hardware-smoke")
    args = parser.parse_args()
    if args.duration <= 0:
        parser.error("--duration must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    if args.simultaneous:
        results.extend(_run_group(args.device_id, args.duration, args.output))
    else:
        for device_id in args.device_id:
            results.extend(_run_group([device_id], args.duration, args.output))
    report = {
        "rx_only": True,
        "simultaneous": bool(args.simultaneous),
        "duration_s": args.duration,
        "results": results,
    }
    report_path = args.output / ("simultaneous.json" if args.simultaneous else "sequential.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Report: {report_path.resolve()}")
    return 0 if results and all(item.get("ok") for item in results) else 1


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
