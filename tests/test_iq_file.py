import struct
import socket
import tempfile
import time
import unittest
from copy import deepcopy
from pathlib import Path

import numpy as np

from sdr_bridge.iq_file import IQFileSource, frequency_from_filename, inspect_iq_wav
from sdr_bridge.app import AppRuntime
from sdr_bridge.config import DEFAULT_CONFIG
from sdr_bridge.model import Discontinuity, RadioConfig, SampleFormat
from sdr_bridge.source import SimulatedSource
from sdr_bridge.udp import parse_datagram


def write_iq_wav(path: Path, samples: np.ndarray, sample_rate: int, *, codec: int = 1, bits: int = 16, auxi_frequency: int | None = None) -> None:
    payload = samples.tobytes()
    block_align = 2 * bits // 8
    fmt = struct.pack("<HHIIHH", codec, 2, sample_rate, sample_rate * block_align, block_align, bits)
    auxi = b"" if auxi_frequency is None else bytes(32) + struct.pack("<I", auxi_frequency) + bytes(128)
    auxi_chunk = b"" if not auxi else struct.pack("<4sI", b"auxi", len(auxi)) + auxi
    riff_size = 4 + 8 + len(fmt) + len(auxi_chunk) + 8 + len(payload)
    path.write_bytes(
        struct.pack("<4sI4s", b"RIFF", riff_size, b"WAVE")
        + struct.pack("<4sI", b"fmt ", len(fmt)) + fmt
        + auxi_chunk
        + struct.pack("<4sI", b"data", len(payload)) + payload
    )


class IQFileTests(unittest.TestCase):
    def test_hdsdr_sdrpp_stereo_wav_is_replayed_and_identified(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "SDRSharp_20261106_103.5MHz_IQ.wav"
            expected = np.arange(46, dtype="<i2").reshape(-1, 2)
            write_iq_wav(path, expected, 2_000_000)

            info = inspect_iq_wav(path)
            self.assertEqual(info.sample_rate_sps, 2_000_000)
            self.assertEqual(info.center_frequency_hz, 103_500_000)
            self.assertEqual(info.sample_count, len(expected))
            self.assertEqual(info.output_format, SampleFormat.CS16)

            source = IQFileSource(path, block_samples=7, realtime=False)
            source.open(source.device_id)
            effective = source.configure(RadioConfig(revision=4))
            chunks, errors = [], []
            source.start(chunks.append, errors.append)
            deadline = time.monotonic() + 2
            while not source.eof and time.monotonic() < deadline:
                time.sleep(.005)
            source.stop()

            self.assertFalse(errors)
            self.assertIn("Fichier IQ int16", source.name)
            self.assertEqual(effective.sample_rate_sps, 2_000_000)
            self.assertEqual(effective.center_frequency_hz, 103_500_000)
            self.assertEqual(sum(chunk.sample_count for chunk in chunks), len(expected))
            self.assertEqual(chunks[0].discontinuity, Discontinuity.START)
            self.assertEqual(b"".join(bytes(chunk.payload) for chunk in chunks), expected.tobytes())

            config = deepcopy(DEFAULT_CONFIG)
            config["source"] = "file"
            config["device_id"] = "stale-hardware-id"
            config["iq_file"] = {"path": str(path), "center_frequency_hz": None, "loop": False}
            config["network"]["legacy_control_port"] = 0
            runtime = AppRuntime(config)
            try:
                self.assertEqual(runtime.bridge.device_id, runtime.bridge.source.device_id)
            finally:
                runtime.close()

            live_config = deepcopy(DEFAULT_CONFIG)
            live_config["source"] = "simulated"
            live_config["network"]["legacy_control_port"] = 0
            live_config["network"]["control_port"] = 0
            live = AppRuntime(live_config)
            original_source = live.bridge.source
            receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            receiver.bind(("127.0.0.1", 0))
            receiver.settimeout(3)
            try:
                live.start(start_rx=False)
                self.assertFalse(live.bridge.running)
                live.add_udp_destination(
                    f"127.0.0.1:{receiver.getsockname()[1]}", "sdbu_v2", 192_000,
                )
                live.select_iq_file(str(path), loop=True)
                self.assertTrue(live.bridge.running)
                self.assertIsInstance(live.bridge.source, IQFileSource)
                self.assertEqual(live.bridge.config.center_frequency_hz, 103_500_000)
                self.assertEqual(live.bridge.config.sample_rate_sps, 2_000_000)
                deadline = time.monotonic() + 3
                decoded = None
                while time.monotonic() < deadline:
                    candidate = parse_datagram(receiver.recvfrom(9000)[0])
                    if candidate.center_frequency_hz == 103_500_000:
                        decoded = candidate
                        break
                self.assertIsNotNone(decoded)
                self.assertEqual(decoded.sample_rate_sps, 192_000)
                live.select_source_device(SimulatedSource.DEVICE_ID)
                self.assertTrue(live.bridge.running)
                self.assertIs(live.bridge.source, original_source)
            finally:
                live.close()
                receiver.close()

    def test_uint8_and_float32_are_converted_to_bridge_formats(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            uint8_path = root / "capture_144300kHz.wav"
            uint8 = np.array([[0, 128], [255, 64]], dtype=np.uint8)
            write_iq_wav(uint8_path, uint8, 192_000, bits=8)
            source = IQFileSource(uint8_path, realtime=False)
            source.open()
            self.assertEqual(source.configure(RadioConfig()).sample_format, SampleFormat.CS16)
            self.assertEqual(
                np.frombuffer(source._convert(uint8.tobytes()), dtype="<i2").tolist(),
                [-32768, 0, 32512, -16384],
            )

            float_path = root / "SDR++_14.074MHz.wav"
            floating = np.array([[.25, -.5], [1.0, 0.0]], dtype="<f4")
            write_iq_wav(float_path, floating, 1_000_000, codec=3, bits=32)
            floating_source = IQFileSource(float_path, realtime=False)
            floating_source.open()
            self.assertEqual(floating_source.configure(RadioConfig()).sample_format, SampleFormat.CS16)
            converted = np.frombuffer(floating_source._convert(floating.tobytes()), dtype="<i2")
            self.assertEqual(converted.tolist(), [8192, -16384, 32767, 0])

    def test_frequency_override_and_invalid_mono_are_explicit(self):
        self.assertEqual(frequency_from_filename("foo_1.296GHz_IQ.wav"), 1_296_000_000)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.wav"
            samples = np.arange(8, dtype="<i2")
            write_iq_wav(path, samples.reshape(-1, 2), 96_000)
            source = IQFileSource(path, center_frequency_hz=7_074_000)
            source.open()
            self.assertEqual(source.configure(RadioConfig()).center_frequency_hz, 7_074_000)

            auxi_path = Path(directory) / "HDSDR_144091kHz_RF.wav"
            write_iq_wav(auxi_path, samples.reshape(-1, 2), 2_000_000, auxi_frequency=144_091_210)
            self.assertEqual(inspect_iq_wav(auxi_path).center_frequency_hz, 144_091_210)

            rf64_path = Path(directory) / "SDR++_7.074MHz_RF64.wav"
            payload = samples.tobytes()
            fmt = struct.pack("<HHIIHH", 1, 2, 96_000, 384_000, 4, 16)
            ds64 = struct.pack("<QQQI", 0, len(payload), len(samples) // 2, 0)
            rf64_path.write_bytes(
                struct.pack("<4sI4s", b"RF64", 0xFFFFFFFF, b"WAVE")
                + struct.pack("<4sI", b"ds64", len(ds64)) + ds64
                + struct.pack("<4sI", b"fmt ", len(fmt)) + fmt
                + struct.pack("<4sI", b"data", 0xFFFFFFFF) + payload
            )
            rf64 = inspect_iq_wav(rf64_path)
            self.assertEqual((rf64.sample_rate_sps, rf64.sample_count), (96_000, len(samples) // 2))
