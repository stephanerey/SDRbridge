from __future__ import annotations

import io
import json
import logging
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

from copy import deepcopy

from sdr_bridge.app import AppRuntime, main
from sdr_bridge.config import DEFAULT_CONFIG
from sdr_bridge.logging_setup import configure_logging, default_log_directory


def read_json_lines(paths: list[Path]) -> list[dict]:
    records = []
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            records.append(json.loads(line))
    return records


class LoggingTests(unittest.TestCase):
    def test_default_windows_directory_is_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": directory}, clear=False):
                self.assertEqual(default_log_directory(), Path(directory) / "SDRbridge" / "logs")
                self.assertEqual(
                    default_log_directory("rsp1"),
                    Path(directory) / "SDRbridge" / "instances" / "rsp1" / "logs",
                )

    def test_json_log_rotates_and_keeps_run_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            session = configure_logging(
                "DEBUG",
                directory,
                run_id="run-test",
                max_bytes=600,
                backup_count=2,
                enable_fault_handler=False,
                stream=False,
                chain_exception_hooks=False,
            )
            try:
                logger = logging.getLogger("sdr_bridge.test")
                for index in range(30):
                    logger.info(
                        "rotation record %s %s",
                        index,
                        "x" * 80,
                        extra={"code": "ROTATION_TEST", "source_id": "source-0", "epoch": "1"},
                    )
            finally:
                session.close()
            files = sorted(Path(directory).glob("sdrbridge.log*"))
            self.assertGreaterEqual(len(files), 2)
            records = read_json_lines(files)
            self.assertTrue(records)
            self.assertTrue(all(item["run_id"] == "run-test" for item in records))
            self.assertTrue(any(item["code"] == "ROTATION_TEST" for item in records))
            self.assertTrue(all("timestamp" in item and "component" in item for item in records))

    def test_invalid_configuration_is_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "invalid.json"
            config.write_text("{invalid", encoding="utf-8")
            with mock.patch("sys.stdout", new=io.StringIO()), mock.patch("sys.stderr", new=io.StringIO()):
                result = main(["--config", str(config), "--log-dir", str(root / "logs")])
            self.assertEqual(result, 2)
            records = read_json_lines([root / "logs" / "sdrbridge.log"])
            self.assertTrue(any(item["code"] == "CONFIG_INVALID" for item in records))
            self.assertTrue(any("invalid JSON file" in item.get("exception", "") for item in records))

    def test_simulated_runtime_records_clean_lifecycle_and_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            session = configure_logging(
                "INFO",
                directory,
                run_id="runtime-test",
                enable_fault_handler=False,
                stream=False,
                chain_exception_hooks=False,
            )
            config = deepcopy(DEFAULT_CONFIG)
            config["network"] = deepcopy(DEFAULT_CONFIG["network"])
            config["network"]["legacy_control_port"] = 0
            runtime = AppRuntime(config, run_id=session.run_id)
            runtime.log_path = session.log_path
            try:
                runtime.start(start_rx=True)
                deadline = time.monotonic() + 1.0
                while runtime.bridge.blocks_written == 0 and time.monotonic() < deadline:
                    time.sleep(0.01)
            finally:
                runtime.close()
                session.close()
            records = read_json_lines([Path(directory) / "sdrbridge.log"])
            codes = [item["code"] for item in records]
            self.assertIn("RUNTIME_START", codes)
            self.assertIn("RUNTIME_READY", codes)
            self.assertIn("RUNTIME_STOP", codes)
            self.assertIn("RUNTIME_STOPPED", codes)
            stop_record = next(item for item in records if item["code"] == "RUNTIME_STOP")
            self.assertEqual(stop_record["run_id"], "runtime-test")
            self.assertGreater(stop_record["details"]["blocks_written"], 0)


if __name__ == "__main__":
    unittest.main()
