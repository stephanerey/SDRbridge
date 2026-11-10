from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import zipfile

from sdr_bridge.diagnostics import export_diagnostic_bundle, sanitize


class DiagnosticBundleTests(unittest.TestCase):
    def test_sanitize_redacts_nested_credentials(self):
        clean = sanitize({"network": {"token": "abc", "password_file": "secret.txt"}, "rate": 2_000_000})
        self.assertEqual(clean["network"]["token"], "<redacted>")
        self.assertEqual(clean["network"]["password_file"], "<redacted>")
        self.assertEqual(clean["rate"], 2_000_000)

    def test_export_contains_sanitized_report_config_and_log_tail(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            log = root / "sdrbridge.jsonl"
            log.write_text('{"token":"abc","message":"ok"}\n', encoding="utf-8")
            result = export_diagnostic_bundle(
                root / "report",
                app_version="0.6.0",
                diagnostics={"state": "RUNNING"},
                configuration={"network": {"token_file": "private.txt"}},
                log_path=log,
            )
            self.assertEqual(result.suffix, ".zip")
            with zipfile.ZipFile(result) as archive:
                self.assertIn("report.json", archive.namelist())
                self.assertIn("logs/sdrbridge-recent.jsonl", archive.namelist())
                config = json.loads(archive.read("configuration.json"))
                self.assertEqual(config["network"]["token_file"], "<redacted>")
                self.assertNotIn("abc", archive.read("logs/sdrbridge-recent.jsonl").decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
