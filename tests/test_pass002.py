import multiprocessing
import random
import threading
import time
import unittest

import numpy as np
from scipy import signal

from sdr_bridge.bridge import SDRBridge, StaleConfigError
from sdr_bridge.dsp import (
    DSPPipeline,
    StreamingRationalResampler,
    complex_to_payload,
    design_resampler_filter,
    payload_to_complex,
)
from sdr_bridge.model import (
    Discontinuity,
    IQBlock,
    RadioConfig,
    SampleFormat,
    TimeDomain,
    TimestampOrigin,
)
from sdr_bridge.profiles import PipelinePool, ProfileRegistry
from sdr_bridge.rf_profiles import RFProfileSet, RFRule
from sdr_bridge.ring import RingReader, SharedIQRing
from sdr_bridge.source import SimulatedSource


def _ring_reader_process(descriptor, ready, result):
    ring = SharedIQRing.attach(descriptor)
    reader = RingReader(ring, start_at_latest=False)
    accepted = torn = 0
    ready.set()
    deadline = time.monotonic() + 1.5
    try:
        while time.monotonic() < deadline:
            block = reader.read(0.02)
            if block is None:
                continue
            data = bytes(block.payload)
            expected = block.sequence.to_bytes(8, "little")
            if data != expected * (block.sample_count * 4 // 8):
                torn += 1
            accepted += 1
        result.put((accepted, torn, reader.dropped_blocks))
    finally:
        ring.close()


class CoreLifecycleTests(unittest.TestCase):
    def test_100_cycles_and_stale_revision(self):
        bridge = SDRBridge(SimulatedSource(block_samples=256), block_samples=256, slots=8)
        try:
            for _ in range(100):
                bridge.start()
                with self.assertRaises(RuntimeError):
                    bridge.start()
                bridge.stop()
            bridge.start()
            previous_epoch = bridge.epoch
            updated = bridge.apply_config(bridge.config.revision, {"center_frequency_hz": 145_000_000})
            self.assertEqual(updated.center_frequency_hz, 145_000_000)
            self.assertGreater(bridge.epoch, previous_epoch)
            with self.assertRaises(StaleConfigError):
                bridge.apply_config(1, {"center_frequency_hz": 146_000_000})
        finally:
            bridge.close()

    def test_simulation_positive_frequency_and_phase_continuity(self):
        bridge = SDRBridge(SimulatedSource(block_samples=4096), block_samples=4096)
        client_id = None
        try:
            bridge.start()
            client_id, reader = bridge.register_client("spectrum")
            first = reader.read(1)
            second = reader.read(1)
            self.assertIsNotNone(first)
            self.assertIsNotNone(second)
            samples = np.concatenate((payload_to_complex(first.payload, first.sample_format), payload_to_complex(second.payload, second.sample_format)))
            spectrum = np.fft.fftshift(np.fft.fft(samples))
            frequencies = np.fft.fftshift(np.fft.fftfreq(len(samples), 1 / first.sample_rate_sps))
            self.assertAlmostEqual(float(frequencies[np.argmax(np.abs(spectrum))]), 10_000.0, delta=300.0)
            self.assertEqual(second.first_sample_index, first.first_sample_index + first.sample_count)
        finally:
            if client_id:
                bridge.unregister_client(client_id)
            bridge.close()

    def test_hot_rf_change_does_not_rebuild_dsp_pipeline(self):
        bridge = SDRBridge(SimulatedSource(block_samples=512), block_samples=512, slots=16)
        client_id = None
        try:
            bridge.start()
            client_id, reader = bridge.register_client("hot", "antrack-192k", 1)
            self.assertIsNotNone(reader)
            before = bridge.status()["pipelines"]
            started = time.perf_counter()
            bridge.apply_config(bridge.config.revision, {"center_frequency_hz": 145_000_000})
            elapsed = time.perf_counter() - started
            self.assertLess(elapsed, 0.5)
            self.assertEqual(len(bridge.status()["pipelines"]), len(before))
            self.assertTrue(bridge.running)
        finally:
            if client_id:
                bridge.unregister_client(client_id)
            bridge.close()

    def test_hot_rf_change_reaches_existing_reader_without_sequence_stall(self):
        """Le chemin contrôle -> flux doit rester observable immédiatement.

        Ce test reproduit le symptôme matériel : un lecteur déjà connecté ne
        doit pas attendre que la séquence réinitialisée rattrape son ancienne
        valeur après une modification de fréquence.
        """
        bridge = SDRBridge(SimulatedSource(block_samples=512), block_samples=512, slots=32)
        client_id = None
        try:
            bridge.start()
            client_id, reader = bridge.register_client("control-latency")
            first = reader.read(1.0)
            self.assertIsNotNone(first)
            started = time.perf_counter()
            bridge.apply_config(bridge.config.revision, {"center_frequency_hz": 145_000_000})
            updated = None
            while time.perf_counter() - started < 0.5:
                candidate = reader.read(0.05)
                if candidate is not None and candidate.center_frequency_hz == 145_000_000:
                    updated = candidate
                    break
            elapsed = time.perf_counter() - started
            self.assertIsNotNone(updated)
            self.assertGreater(updated.sequence, first.sequence)
            self.assertEqual(updated.center_frequency_hz, 145_000_000)
            self.assertLess(elapsed, 0.5)
        finally:
            if client_id:
                bridge.unregister_client(client_id)
            bridge.close()


class RingV2Tests(unittest.TestCase):
    def test_layout_and_multiprocess_wrap_are_coherent(self):
        ring = SharedIQRing(8, 64)
        context = multiprocessing.get_context("spawn")
        ready = context.Event()
        result = context.Queue()
        process = context.Process(target=_ring_reader_process, args=(ring.descriptor.to_dict(), ready, result))
        process.start()
        self.assertTrue(ready.wait(5))
        try:
            for sequence in range(5000):
                pattern = sequence.to_bytes(8, "little") * 32
                block = IQBlock(
                    "source-0", 1, sequence, sequence * 64, 64, 2_000_000, 144_300_000, 1,
                    SampleFormat.CS16, time.monotonic_ns(), TimeDomain.HOST_MONOTONIC,
                    TimestampOrigin.HOST_OBSERVATION,
                    Discontinuity.START if sequence == 0 else Discontinuity.NONE, 0, memoryview(pattern),
                )
                ring.write(block)
                if sequence % 32 == 0:
                    time.sleep(0)
            accepted, torn, dropped = result.get(timeout=5)
            self.assertGreater(accepted, 0)
            self.assertEqual(torn, 0)
            self.assertGreaterEqual(dropped, 0)
            self.assertEqual(ring.descriptor.slot_stride % 64, 0)
        finally:
            process.join(5)
            if process.is_alive():
                process.terminate()
            ring.close(unlink=True)


class DSPTests(unittest.TestCase):
    def test_format_conversion_saturation_and_nonfinite(self):
        values = np.array([-2-2j, -1-.5j, 0+0j, .5+1j, 2+2j], np.complex64)
        payload = complex_to_payload(values, SampleFormat.CS16)
        scalars = np.frombuffer(payload, dtype="<i2").reshape(-1, 2)
        self.assertEqual(tuple(scalars[0]), (-32768, -32768))
        self.assertEqual(tuple(scalars[-1]), (32767, 32767))
        recovered = payload_to_complex(payload, SampleFormat.CS16)
        self.assertAlmostEqual(float(recovered[3].real), .5, places=4)
        with self.assertRaises(ValueError):
            complex_to_payload(np.array([np.nan + 0j]), SampleFormat.CF32)

    def test_filter_targets_and_partition_invariance(self):
        rng = np.random.default_rng(1)
        data = (rng.standard_normal(20000) + 1j * rng.standard_normal(20000)).astype(np.complex64) * .01
        for output_rate in (192_000, 96_000):
            taps, metrics = design_resampler_filter(2_000_000, output_rate)
            self.assertLessEqual(metrics.passband_ripple_db, .1)
            self.assertGreaterEqual(metrics.stopband_attenuation_db, 80.0)
            whole = StreamingRationalResampler(2_000_000, output_rate).process(data)
            streaming = StreamingRationalResampler(2_000_000, output_rate)
            parts = []
            offset = 0
            random.seed(1)
            while offset < len(data):
                size = random.randint(1, 997)
                parts.append(streaming.process(data[offset:offset + size]))
                offset += size
            partitioned = np.concatenate(parts)
            self.assertEqual(len(whole), len(partitioned))
            np.testing.assert_allclose(whole, partitioned, rtol=2e-5, atol=2e-6)

    def test_pipeline_pool_mutualizes_equivalent_profiles(self):
        registry = ProfileRegistry()
        pool = PipelinePool("source-a", 2_000_000, SampleFormat.CS16)
        outputs = [[], []]
        token1, processor1 = pool.subscribe(registry.get("antrack-192k", 1), outputs[0].append)
        token2, processor2 = pool.subscribe(registry.get("native-cf32-192k", 1), outputs[1].append)
        self.assertIsNot(processor1, processor2)  # formats de sortie distincts
        token3, processor3 = pool.subscribe(registry.get("antrack-192k", 1), outputs[1].append)
        self.assertIs(processor1, processor3)
        self.assertEqual(pool.pipeline_count, 2)
        pool.unsubscribe(token1); pool.unsubscribe(token3)
        self.assertEqual(pool.pipeline_count, 1)
        pool.unsubscribe(token2)
        self.assertEqual(pool.pipeline_count, 0)


class RFProfileTests(unittest.TestCase):
    def test_boundaries_ambiguity_and_manual_suspend(self):
        profiles = RFProfileSet()
        profiles.add(RFRule("low", 100, 200, 1))
        profiles.add(RFRule("high", 200, 300, 1))
        self.assertEqual(profiles.select(199, "dev").rule_id, "low")
        self.assertEqual(profiles.select(200, "dev").rule_id, "high")
        with self.assertRaises(ValueError):
            profiles.add(RFRule("ambiguous", 150, 250, 1))
        profiles.suspend_manual()
        self.assertIsNone(profiles.select(199, "dev"))
        profiles.resume()
        self.assertEqual(profiles.select(199, "dev").rule_id, "low")


if __name__ == "__main__":
    unittest.main()
