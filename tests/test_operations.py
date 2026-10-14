import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest import mock

import numpy as np

from sdr_bridge.bridge import SDRBridge
from sdr_bridge.config import DEFAULT_CONFIG, atomic_write_json, load_app_config, read_json, save_app_config
from sdr_bridge.model import Discontinuity, IQBlock, RadioConfig, SampleFormat, TimeDomain, TimestampOrigin
from sdr_bridge.recording import ReplaySource, SigMFRecorder, validate_sigmf
from sdr_bridge.source import SimulatedSource


def make_block(sequence, discontinuity=Discontinuity.NONE, epoch=1, count=16):
    payload = np.arange(count * 2, dtype="<i2").tobytes()
    return IQBlock(
        "source-0", epoch, sequence, sequence * count, count, 192_000, 144_300_000, 1,
        SampleFormat.CS16, sequence * 1_000_000, TimeDomain.HOST_MONOTONIC,
        TimestampOrigin.HOST_OBSERVATION, discontinuity, 0, memoryview(payload),
    )


class ConfigTests(unittest.TestCase):
    def test_round_trip_unknown_version_and_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "app.json"
            save_app_config(path, DEFAULT_CONFIG)
            loaded_path, value = load_app_config(path)
            self.assertEqual(loaded_path, path)
            self.assertEqual(value, DEFAULT_CONFIG)
            original = path.read_bytes()
            bad = dict(DEFAULT_CONFIG); bad["schema_version"] = 2
            path.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_app_config(path)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["schema_version"], 2)
            path.write_text("{bad", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_app_config(path)

    def test_atomic_failure_keeps_previous_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "app.json"
            save_app_config(path, DEFAULT_CONFIG)
            previous = path.read_bytes()
            with mock.patch("sdr_bridge.config.os.replace", side_effect=OSError("injected")):
                with self.assertRaises(OSError):
                    save_app_config(path, DEFAULT_CONFIG)
            self.assertEqual(path.read_bytes(), previous)


class RecordingTests(unittest.TestCase):
    def test_capture_validate_replay_seek_and_eof(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "capture"
            recorder = SigMFRecorder(base, 192_000, SampleFormat.CS16, 144_300_000)
            recorder.start()
            recorder.enqueue(make_block(0, Discontinuity.START))
            recorder.enqueue(make_block(1))
            recorder.stop("arrêt demandé")
            self.assertTrue(recorder.finalized)
            meta = json.loads(Path(str(base) + ".sigmf-meta").read_text(encoding="utf-8"))
            count = validate_sigmf(meta, Path(str(base) + ".sigmf-data"))
            self.assertEqual(count, 32)
            self.assertNotIn("core:dataset", meta["global"])
            self.assertNotIn("core:datetime", meta["captures"][0])

            replay = ReplaySource(base, block_samples=7, realtime=False)
            replay.open(replay.device_id)
            effective = replay.configure(RadioConfig(revision=3))
            self.assertEqual(effective.sample_rate_sps, 192_000)
            chunks = []
            errors = []
            replay.start(chunks.append, errors.append)
            deadline = time.monotonic() + 2
            while not replay.eof and time.monotonic() < deadline:
                time.sleep(.01)
            replay.stop()
            self.assertFalse(errors)
            self.assertEqual(sum(item.sample_count for item in chunks), 32)
            replay.seek(10)
            chunks.clear(); replay.start(chunks.append, errors.append)
            while not replay.eof and time.monotonic() < deadline + 2:
                time.sleep(.01)
            replay.stop()
            self.assertEqual(chunks[0].discontinuity, Discontinuity.REPLAY_SEEK)

    def test_discontinuity_stops_without_concatenating(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = SigMFRecorder(Path(directory) / "gap", 192_000, SampleFormat.CS16, 1)
            recorder.start()
            recorder.enqueue(make_block(0, Discontinuity.START))
            recorder.enqueue(make_block(1, Discontinuity.SOURCE_LOSS))
            recorder.stop()
            self.assertTrue(recorder.incomplete)
            self.assertIn("discontinuité", recorder.reason)
            self.assertEqual(recorder.samples_written, 16)

    def test_truncated_replay_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "bad"
            data = Path(str(base) + ".sigmf-data")
            meta = Path(str(base) + ".sigmf-meta")
            data.write_bytes(b"123")
            meta.write_text(json.dumps({
                "global": {"core:version": "1.2.6", "core:datatype": "ci16_le", "core:sample_rate": 1, "core:num_channels": 1, "core:recorder": "SDRbridge"},
                "captures": [{"core:sample_start": 0, "core:frequency": 1}], "annotations": [],
            }), encoding="utf-8")
            with self.assertRaises(ValueError):
                ReplaySource(base).open()


class RecoveryTests(unittest.TestCase):
    def test_recovery_succeeds_on_third_attempt_with_injected_wait(self):
        class FlakySource(SimulatedSource):
            def __init__(self):
                super().__init__(block_samples=128)
                self.opens = 0
            def open(self, device_id=SimulatedSource.DEVICE_ID):
                self.opens += 1
                if 2 <= self.opens <= 3:
                    raise RuntimeError("injected open failure")
                return super().open(device_id)

        source = FlakySource()
        bridge = SDRBridge(source, block_samples=128)
        waits = []
        try:
            bridge.start()
            bridge._on_source_error(RuntimeError("injected loss"))
            self.assertTrue(bridge.recover(wait=lambda delay: waits.append(delay) or False))
            self.assertEqual(source.opens, 4)
            self.assertEqual(waits, [1.0, 2.0, 5.0])
            self.assertTrue(bridge.running)
        finally:
            bridge.close()


if __name__ == "__main__":
    unittest.main()
