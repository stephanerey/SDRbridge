import importlib.util
import os
from pathlib import Path
import subprocess
import unittest

import numpy as np

from sdr_bridge.bridge import SDRBridge
from sdr_bridge.control import ControlServer
from sdr_bridge.source import SimulatedSource


class LocalClientCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.bridge = SDRBridge(SimulatedSource(), block_samples=4096)
        self.bridge.start()
        self.control = ControlServer(self.bridge, port=0)
        self.control.start()

    def tearDown(self):
        self.control.close(); self.bridge.close()

    def test_antrack_shim_consumes_shared_filtered_profile(self):
        path = Path(__file__).resolve().parents[1] / "clients" / "antrack" / "SoapySDR.py"
        spec = importlib.util.spec_from_file_location("sdrbridge_test_soapy", path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        module.CONTROL_HOST, module.CONTROL_PORT = self.control.address
        device = module.Device()
        try:
            device.setSampleRate(module.SOAPY_SDR_RX, 0, 96_000)
            stream = device.setupStream(module.SOAPY_SDR_RX, module.SOAPY_SDR_CF32)
            device.activateStream(stream)
            output = np.empty(2048, dtype=np.complex64)
            result = device.readStream(stream, [output], len(output), timeoutUs=3_000_000)
            self.assertEqual(result.ret, len(output))
            self.assertTrue(np.isfinite(output).all())
            before = self.bridge.config
            device.setFrequency(module.SOAPY_SDR_RX, 0, 999_000_000)
            self.assertEqual(self.bridge.config, before)
            self.assertEqual(self.bridge._pipelines.pipeline_count, 1)
        finally:
            device._disconnect()

    def test_extio_win32_smoke_reads_owned_v2_copies(self):
        directory = Path(__file__).resolve().parents[1] / "native" / "build" / "extio_bridge" / "Release"
        env = os.environ.copy()
        env["SDRBRIDGE_CONTROL_PORT"] = str(self.control.address[1])
        env["SDRBRIDGE_EXPECTED_FREQUENCY"] = str(self.bridge.config.center_frequency_hz)
        result = subprocess.run(
            [str(directory / "extio_smoke.exe")], cwd=directory, env=env,
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("samples=", result.stdout)
        self.assertIn("lo_events=1", result.stdout)


if __name__ == "__main__":
    unittest.main()
