from __future__ import annotations

import argparse
import atexit
from collections import deque
import ctypes
from ctypes import wintypes
import json
import math
import os
from pathlib import Path
import socket
import statistics
import sys
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "windows")

from PyQt5 import QtWidgets

from sdr_bridge.bridge import SDRBridge
from sdr_bridge.gui import BridgeWindow
from sdr_bridge.logging_setup import configure_logging
from sdr_bridge.native_client import NativeIQClient
from sdr_bridge.native_control import NativeControlServer
from sdr_bridge.recording import SigMFRecorder, validate_sigmf
from sdr_bridge.source import SimulatedSource


class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


_get_current_process = ctypes.windll.kernel32.GetCurrentProcess
_get_current_process.argtypes = []
_get_current_process.restype = wintypes.HANDLE
_get_process_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
_get_process_memory_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS_EX), wintypes.DWORD]
_get_process_memory_info.restype = wintypes.BOOL


def private_bytes() -> int:
    counters = PROCESS_MEMORY_COUNTERS_EX(); counters.cb = ctypes.sizeof(counters)
    handle = _get_current_process()
    if not _get_process_memory_info(handle, ctypes.byref(counters), counters.cb):
        raise OSError("GetProcessMemoryInfo failed")
    return int(counters.PrivateUsage)


def percentile(values: list[float], percentile_value: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(percentile_value / 100 * len(ordered)) - 1))
    return float(ordered[index])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--warmup", type=float, default=300.0)
    parser.add_argument("--label", required=True)
    parser.add_argument("--output", default="output/qualification")
    parser.add_argument("--capture-seconds", type=float, default=0.0)
    parser.add_argument("--no-gui", action="store_true", help="comparatif moteur sans fenêtre Qt")
    args = parser.parse_args()
    output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
    log_session = configure_logging("INFO", output / "logs", stream=False)
    atexit.register(log_session.close)
    import logging
    logger = logging.getLogger("sdr_bridge.qualification")
    logger.info(
        "simulation qualification started",
        extra={"code": "QUALIFICATION_START", "details": {"label": args.label, "duration_s": args.duration, "warmup_s": args.warmup}},
    )
    source = SimulatedSource(block_samples=4096, tone_hz=10_000, amplitude=.25, seed=1)
    bridge = SDRBridge(source, block_samples=4096, slots=64, run_id=log_session.run_id)
    server = NativeControlServer(bridge, port=0)
    readers = []
    reader_threads = []
    reader_stop = threading.Event()
    reader_counts = []
    clients: list[NativeIQClient] = []
    udp_threads = []
    udp_stop = threading.Event()
    udp_results = [{
        "packets": 0,
        "samples": 0,
        "gaps": 0,
        "latency_ms": deque(maxlen=100_000),
        "latency_observations": 0,
        "last": None,
    } for _ in range(2)]
    app = None if args.no_gui else (QtWidgets.QApplication.instance() or QtWidgets.QApplication([]))
    window = None
    recorder = None; recorder_token = None
    prewarm_token = None
    started_wall = 0.0; started_cpu = 0.0
    memory_samples: list[tuple[float, int]] = []
    queue_drop_events: list[dict] = []
    result: dict = {"label": args.label, "duration_requested_s": args.duration, "warmup_s": args.warmup}

    def local_worker(index, reader, client_id):
        blocks = samples = 0
        while not reader_stop.is_set():
            block = reader.read(.2)
            if block:
                blocks += 1; samples += block.sample_count
                bridge.record_read(client_id, block.sequence, samples, reader.dropped_blocks)
        reader_counts[index] = {"blocks": blocks, "samples": samples, "drops": reader.dropped_blocks, "torn_retries": reader.torn_retries_exhausted}

    def udp_worker(index, client):
        state = udp_results[index]
        next_heartbeat = time.monotonic() + 4.0
        while not udp_stop.is_set():
            if time.monotonic() >= next_heartbeat:
                client.heartbeat(); next_heartbeat = time.monotonic() + 4.0
            try:
                packet = client.receive(.2)
            except socket.timeout:
                continue
            state["packets"] += 1; state["samples"] += packet.sample_count
            if state["last"] is not None and packet.packet_sequence > state["last"] + 1:
                state["gaps"] += packet.packet_sequence - state["last"] - 1
            state["last"] = packet.packet_sequence
            if packet.timestamp_ns:
                latency = (time.monotonic_ns() - packet.timestamp_ns) / 1_000_000
                if 0 <= latency <= 10_000:
                    state["latency_observations"] += 1
                    # Échantillonnage déterministe borné : la fixture ne doit pas
                    # devenir elle-même une fuite pendant l'endurance d'une heure.
                    if state["latency_observations"] % 10 == 0:
                        state["latency_ms"].append(latency)

    try:
        bridge.open()
        for index in range(5):
            client_id, reader = bridge.register_client(f"qualification-local-{index}")
            readers.append((client_id, reader)); reader_counts.append({})
            thread = threading.Thread(target=local_worker, args=(index, reader, client_id), daemon=True)
            reader_threads.append(thread); thread.start()
        profile_client_id, profile_reader = bridge.register_client("qualification-96k", "antrack-96k", 1)
        readers.append((profile_client_id, profile_reader)); reader_counts.append({})
        thread = threading.Thread(target=local_worker, args=(5, profile_reader, profile_client_id), daemon=True)
        reader_threads.append(thread); thread.start()
        if app is not None:
            window = BridgeWindow(bridge); window.show(); app.processEvents()
        # Construire le profil DSP natif avant l'acquisition. Le protocole interdit
        # l'abonnement réseau hors RUNNING, mais aucun travail lourd ne doit rester
        # dans la courte fenêtre d'inscription qui suit le start.
        prewarm_token, _ = bridge.subscribe_profile("native-cs16-192k", 1, lambda block: None)
        server.start()
        bridge.start()
        started_wall = time.monotonic(); started_cpu = time.process_time()
        last_queue_drops = bridge.source_queue_drops
        queue_drop_events.append({"at_s": 0.0, "stage": "source_started", "total": last_queue_drops})
        for index in range(2):
            client = NativeIQClient(*server.address, profile_id="native-cs16-192k")
            clients.append(client)
            thread = threading.Thread(target=udp_worker, args=(index, client), daemon=True)
            udp_threads.append(thread); thread.start()
            queue_drop_events.append({"at_s": time.monotonic() - started_wall, "stage": f"udp_client_{index + 1}", "total": bridge.source_queue_drops})
        if args.capture_seconds > 0:
            base = output / f"{args.label}-capture"
            for suffix in (".sigmf-data", ".sigmf-meta"):
                candidate = Path(str(base) + suffix)
                if candidate.exists():
                    candidate.unlink()
            recorder = SigMFRecorder(base, 192_000, bridge.profiles.get("native-cs16-192k", 1).sample_format, bridge.config.center_frequency_hz)
            recorder.start(); recorder_token, _ = bridge.subscribe_profile("native-cs16-192k", 1, recorder.enqueue)
        bridge.unsubscribe_profile(prewarm_token); prewarm_token = None
        queue_drop_events.append({"at_s": time.monotonic() - started_wall, "stage": "outputs_armed", "total": bridge.source_queue_drops})
        next_sample = started_wall; next_progress = started_wall + 30
        last_drop_trace = started_wall
        capture_stopped = False
        while True:
            now = time.monotonic(); elapsed = now - started_wall
            if elapsed >= args.duration:
                break
            if app is not None:
                app.processEvents()
            if bridge.source_queue_drops != last_queue_drops:
                last_queue_drops = bridge.source_queue_drops
                if len(queue_drop_events) == 4 or now - last_drop_trace >= 1.0:
                    queue_drop_events.append({"at_s": elapsed, "stage": "measurement", "total": last_queue_drops})
                    last_drop_trace = now
            if recorder and not capture_stopped and elapsed >= args.capture_seconds:
                bridge.unsubscribe_profile(recorder_token); recorder.stop("fin de la fixture de qualification"); capture_stopped = True
            if now >= next_sample:
                memory_samples.append((elapsed, private_bytes())); next_sample = now + 1
            if now >= next_progress:
                print(json.dumps({"progress_s": round(elapsed, 1), "blocks": bridge.blocks_written, "queue_drops": bridge.source_queue_drops, "private_mib": round(private_bytes()/2**20, 1)}), flush=True)
                next_progress = now + 30
            time.sleep(.02)
        if recorder and not capture_stopped:
            bridge.unsubscribe_profile(recorder_token); recorder.stop("fin de la fixture de qualification"); capture_stopped = True
        elapsed = time.monotonic() - started_wall
        if bridge.source_queue_drops != queue_drop_events[-1]["total"]:
            queue_drop_events.append({"at_s": elapsed, "stage": "measurement_final", "total": bridge.source_queue_drops})
        cpu_total_percent = (time.process_time() - started_cpu) / elapsed / max(1, os.cpu_count() or 1) * 100
        stop_started = time.monotonic()
        # Geler la production avant de désarmer les consommateurs. Cela mesure un
        # arrêt d'exploitation réel et évite de créer artificiellement du trafic
        # pendant la fermeture séquentielle du contrôle et des sockets.
        bridge.stop()
        reader_stop.set(); udp_stop.set()
        for thread in reader_threads + udp_threads:
            thread.join(timeout=2)
        for client in clients:
            client.close()
        if window:
            window.spectrum.close(); window.hide()
        server.close()
        stop_seconds = time.monotonic() - stop_started
        if recorder:
            meta_path = Path(str(output / f"{args.label}-capture") + ".sigmf-meta")
            data_path = Path(str(output / f"{args.label}-capture") + ".sigmf-data")
            capture_samples = validate_sigmf(json.loads(meta_path.read_text(encoding="utf-8")), data_path)
        else:
            capture_samples = 0
        after_warmup = [value for when, value in memory_samples if when >= min(args.warmup, args.duration * .8)]
        baseline_candidates = [value for when, value in memory_samples if when >= min(args.warmup, args.duration * .8)][:5]
        baseline = min(baseline_candidates) if baseline_candidates else (memory_samples[0][1] if memory_samples else private_bytes())
        maximum = max(after_warmup or [value for _, value in memory_samples] or [private_bytes()])
        growth = maximum - baseline
        all_latencies = [value for item in udp_results for value in item["latency_ms"]]
        for item in udp_results:
            retained = list(item.pop("latency_ms"))
            item["latency_retained"] = len(retained)
            item["latency_p95_ms"] = percentile(retained, 95)
            item.pop("last", None)
        result.update({
            "duration_actual_s": elapsed,
            "environment": {"python": sys.version.split()[0], "cpu_count": os.cpu_count(), "pid": os.getpid(), "log_file": str(log_session.log_path) if log_session.log_path else None},
            "source": {
                "blocks": bridge.blocks_written,
                "samples": bridge.samples_written,
                "queue_drops": bridge.source_queue_drops,
                "queue_capacity_blocks": bridge.source_queue_capacity,
                "queue_high_water_blocks": bridge.source_queue_high_water,
                "errors": bridge.source_errors,
                "dispatch_processing_average_ms": bridge.status()["dispatch_processing_average_ms"],
                "dispatch_processing_max_ms": bridge.status()["dispatch_processing_max_ms"],
                "dispatch_slow_blocks": bridge.status()["dispatch_slow_blocks"],
            },
            "source_queue_drop_events": queue_drop_events,
            "local_readers": reader_counts,
            "udp_receivers": udp_results,
            "latency_method": "timestamp host_monotonic du premier échantillon corrélé au recvfrom dans le même processus ; une observation valide sur dix, fenêtre bornée aux 100000 dernières valeurs par destination ; valeurs négatives/non bornées exclues",
            "latency_samples": len(all_latencies),
            "latency_median_ms": statistics.median(all_latencies) if all_latencies else None,
            "latency_p95_ms": percentile(all_latencies, 95),
            "latency_p99_ms": percentile(all_latencies, 99),
            "cpu_average_total_capacity_percent": cpu_total_percent,
            "private_memory_max_mib": maximum / 2**20,
            "private_memory_growth_after_warmup_mib": growth / 2**20,
            "stop_seconds": stop_seconds,
            "capture_samples": capture_samples,
            "gui_active": app is not None,
        })
        fast_readers_ok = all(item.get("drops", 1) == 0 and item.get("torn_retries", 1) == 0 for item in reader_counts[:5])
        udp_ok = all(item["gaps"] == 0 and item["packets"] > 0 for item in udp_results)
        result["criteria"] = {
            "zero_source_queue_drops": bridge.source_queue_drops == 0,
            "source_queue_within_bound": bridge.source_queue_high_water <= bridge.source_queue_capacity,
            "fast_readers_zero_loss": fast_readers_ok,
            "udp_receivers_zero_detected_gap": udp_ok,
            "memory_growth_le_64_mib": growth <= 64 * 2**20,
            "process_memory_le_512_mib": maximum <= 512 * 2**20,
            "cpu_average_le_25_percent_total": cpu_total_percent <= 25.0,
            "latency_p95_le_250_ms": result["latency_p95_ms"] is not None and result["latency_p95_ms"] <= 250.0,
            "stop_le_5_s": stop_seconds <= 5.0,
            "capture_valid": recorder is None or capture_samples > 0,
        }
        result["passed"] = all(result["criteria"].values())
    finally:
        reader_stop.set(); udp_stop.set()
        if recorder and not recorder.finalized:
            try: recorder.stop("arrêt de secours")
            except Exception: pass
        if prewarm_token:
            try: bridge.unsubscribe_profile(prewarm_token)
            except Exception: pass
        for client in clients:
            try: client.close()
            except Exception: pass
        try: server.close()
        except Exception: pass
        try: bridge.close()
        except Exception: pass
    report = output / f"{args.label}.json"
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        "simulation qualification finished",
        extra={"code": "QUALIFICATION_FINISH", "details": {"label": args.label, "passed": result.get("passed"), "report": str(report.resolve()), "criteria": result.get("criteria")}},
    )
    log_session.close()
    atexit.unregister(log_session.close)
    print(json.dumps({"report": str(report.resolve()), "passed": result.get("passed"), "criteria": result.get("criteria")}, ensure_ascii=False), flush=True)
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
