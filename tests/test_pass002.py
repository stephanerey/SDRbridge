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
    design_integer_decimator_filter,
    design_resampler_filter,
    payload_to_complex,
)
from sdr_bridge.model import (
    Discontinuity,
    IQBlock,
    RadioConfig,
    SampleFormat,
    StreamProfile,
    TimeDomain,
    TimestampOrigin,
)
from sdr_bridge.profiles import PipelinePool, ProfileRegistry
from sdr_bridge.rf_profiles import RFProfileSet, RFRule
from sdr_bridge.ring import RingReader, SharedIQRing
from sdr_bridge.source import SimulatedSource, SourceChunk


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
    def test_master_dispatch_is_not_blocked_by_slow_client_dsp(self):
        bridge = SDRBridge(
            SimulatedSource(block_samples=4096),
            RadioConfig(sample_rate_sps=10_000_000, bandwidth_hz=8_000_000),
            block_samples=4096,
            slots=16,
            source_queue_blocks=16,
        )
        original_process = bridge._pipelines.process

        def slow_process(block):
            time.sleep(0.05)
            original_process(block)

        bridge._pipelines.process = slow_process
        try:
            bridge._start_dispatcher()
            payload = memoryview(bytes(4096 * SampleFormat.CS16.bytes_per_iq))
            for index in range(6):
                bridge._on_source_chunk(SourceChunk(
                    payload, 4096, index * 4096, time.monotonic_ns(),
                    TimeDomain.HOST_MONOTONIC, TimestampOrigin.HOST_OBSERVATION,
                ))
            deadline = time.monotonic() + 0.5
            while bridge.blocks_written < 6 and time.monotonic() < deadline:
                time.sleep(0.005)
            self.assertEqual(bridge.blocks_written, 6)
            self.assertLess(bridge.dsp_blocks_processed, bridge.blocks_written)
            self.assertEqual(bridge.source_queue_drops, 0)
        finally:
            bridge._stop_dispatcher()
            bridge.close()

    def test_measured_rate_uses_short_current_interval_after_rate_change(self):
        bridge = SDRBridge(
            SimulatedSource(block_samples=4096),
            RadioConfig(sample_rate_sps=2_000_000, bandwidth_hz=1_536_000),
            block_samples=4096,
            slots=16,
        )
        try:
            bridge.start()
            time.sleep(0.8)
            self.assertAlmostEqual(bridge.status()["sample_rate_measured"], 2_000_000, delta=250_000)
            bridge.apply_config(
                bridge.config.revision,
                {"sample_rate_sps": 192_000, "bandwidth_hz": 192_000},
            )
            time.sleep(0.8)
            self.assertAlmostEqual(bridge.status()["sample_rate_measured"], 192_000, delta=35_000)
        finally:
            bridge.close()

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

    def test_stop_start_keeps_master_and_profile_ring_sequences_monotone(self):
        """Existing readers resume immediately after an RX stop/start cycle."""
        bridge = SDRBridge(SimulatedSource(block_samples=512), block_samples=512, slots=32)
        master_id = profile_id = None
        try:
            bridge.start()
            master_id, master = bridge.register_client("master-restart")
            profile_id, profile = bridge.register_client("profile-restart", "antrack-192k", 1)

            deadline = time.monotonic() + 1.5
            while bridge._sequence < 1_000 and time.monotonic() < deadline:
                time.sleep(0.005)
            before_master = master.read_latest(0.2)
            before_profile = profile.read_latest(0.2)
            self.assertIsNotNone(before_master)
            self.assertIsNotNone(before_profile)

            bridge.stop()
            previous_epoch = bridge.epoch
            bridge.start()
            after_master = master.read(0.2)
            after_profile = profile.read(0.2)

            self.assertIsNotNone(after_master)
            self.assertIsNotNone(after_profile)
            self.assertGreater(bridge.epoch, previous_epoch)
            self.assertGreater(after_master.sequence, before_master.sequence)
            self.assertGreater(after_profile.sequence, before_profile.sequence)
        finally:
            if master_id:
                bridge.unregister_client(master_id)
            if profile_id:
                bridge.unregister_client(profile_id)
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

    def test_integer_decimator_targets_and_high_rate_multistage_partition_invariance(self):
        sos, metrics = design_integer_decimator_filter(10_000_000, 5)
        frequencies, response = signal.sosfreqz(sos, worN=262144)
        normalized = frequencies / np.pi
        passband = np.abs(response[normalized <= 0.8 / 5])
        stopband = np.abs(response[normalized >= 1.0 / 5])
        ripple = float(np.ptp(20.0 * np.log10(np.maximum(passband, 1e-300))))
        attenuation = float(-20.0 * np.log10(max(float(np.max(stopband)), 1e-300)))
        self.assertLessEqual(ripple, metrics.passband_ripple_db + 1e-6)
        self.assertGreaterEqual(attenuation, metrics.stopband_attenuation_db - 1e-6)

        rng = np.random.default_rng(2)
        data = (rng.standard_normal(50000) + 1j * rng.standard_normal(50000)).astype(np.complex64) * .01
        whole_resampler = StreamingRationalResampler(10_000_000, 96_000)
        self.assertIsNotNone(whole_resampler._integer_stage)
        self.assertIsNotNone(whole_resampler._final_stage)
        whole = whole_resampler.process(data)
        streaming = StreamingRationalResampler(10_000_000, 96_000)
        parts = []
        offset = 0
        random.seed(2)
        while offset < len(data):
            size = random.randint(1, 997)
            parts.append(streaming.process(data[offset:offset + size]))
            offset += size
        partitioned = np.concatenate(parts)
        self.assertEqual(len(whole), len(partitioned))
        np.testing.assert_allclose(whole, partitioned, rtol=3e-5, atol=3e-6)

    def test_high_rate_fractional_decimator_is_compact_filtered_and_partition_invariant(self):
        input_rate = 10_000_000
        output_rate = 4_000_000
        optimized = StreamingRationalResampler(input_rate, output_rate)
        self.assertIsNotNone(optimized._prefilter_sos)
        self.assertLess(len(optimized.taps), 64)
        self.assertLessEqual(optimized.characterization.passband_ripple_db, .1)
        self.assertGreaterEqual(optimized.characterization.stopband_attenuation_db, 80.0)

        rng = np.random.default_rng(3)
        data = (
            rng.standard_normal(100_000) + 1j * rng.standard_normal(100_000)
        ).astype(np.complex64) * .01
        whole = optimized.process(data)
        streaming = StreamingRationalResampler(input_rate, output_rate)
        parts = []
        offset = 0
        random.seed(3)
        while offset < len(data):
            size = random.randint(1, 2047)
            parts.append(streaming.process(data[offset:offset + size]))
            offset += size
        partitioned = np.concatenate(parts)
        self.assertEqual(len(whole), len(partitioned))
        np.testing.assert_allclose(whole, partitioned, rtol=3e-5, atol=3e-6)

        sample_indexes = np.arange(200_000)
        pass_tone = np.exp(2j * np.pi * 1_500_000 * sample_indexes / input_rate).astype(np.complex64)
        stop_tone = np.exp(2j * np.pi * 2_500_000 * sample_indexes / input_rate).astype(np.complex64)
        pass_output = StreamingRationalResampler(input_rate, output_rate).process(pass_tone)
        stop_output = StreamingRationalResampler(input_rate, output_rate).process(stop_tone)
        pass_amplitude = float(np.median(np.abs(pass_output[2000:])))
        stop_amplitude = float(np.median(np.abs(stop_output[2000:])))
        self.assertGreater(pass_amplitude, .98)
        self.assertLess(stop_amplitude / pass_amplitude, 1e-4)

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

    def test_pipeline_pool_cascades_lower_rates_from_nearest_shared_parent(self):
        registry = ProfileRegistry()
        pool = PipelinePool("source-a", 10_000_000, SampleFormat.CS16)
        master_outputs = []
        qmap_outputs = []
        pool.subscribe(registry.get("master-cs16", 1), master_outputs.append)
        pool.subscribe(registry.get("antrack-96k", 1), qmap_outputs.append)
        snapshots = {item["output_rate_sps"]: item for item in pool.snapshot()}
        self.assertEqual(snapshots[2_000_000]["input_rate_sps"], 10_000_000)
        self.assertEqual(snapshots[96_000]["input_rate_sps"], 2_000_000)
        self.assertEqual(snapshots[96_000]["shared_parent_rate_sps"], 2_000_000)

        samples = np.zeros((16384, 2), dtype="<i2")
        block = IQBlock(
            "source-a", 1, 0, 0, 16384, 10_000_000, 144_300_000, 1,
            SampleFormat.CS16, 0, TimeDomain.UNKNOWN,
            TimestampOrigin.HOST_OBSERVATION, Discontinuity.NONE, None,
            memoryview(samples.tobytes()),
        )
        pool.process(block)
        self.assertEqual(master_outputs[-1].sample_rate_sps, 2_000_000)
        self.assertEqual(qmap_outputs[-1].sample_rate_sps, 96_000)

    def test_high_rate_parallel_pool_cascades_profiles_on_stage_workers(self):
        registry = ProfileRegistry()
        pool = PipelinePool(
            "source-a",
            10_000_000,
            SampleFormat.CS16,
            parallel_workers=3,
        )
        outputs_4m = []
        outputs_96k = []
        profile_4m = StreamProfile(
            "udp-4m",
            1,
            4_000_000,
            SampleFormat.CS16,
            "sdbu_v2",
            name="UDP 4 MS/s",
        )
        try:
            pool.subscribe(profile_4m, outputs_4m.append)
            pool.subscribe(registry.get("antrack-96k", 1), outputs_96k.append)
            snapshots = {item["output_rate_sps"]: item for item in pool.snapshot()}
            self.assertEqual(snapshots[4_000_000]["input_rate_sps"], 10_000_000)
            self.assertEqual(snapshots[96_000]["input_rate_sps"], 4_000_000)
            self.assertIsNone(snapshots[4_000_000]["shared_parent_rate_sps"])
            self.assertEqual(snapshots[96_000]["shared_parent_rate_sps"], 4_000_000)

            samples = np.zeros((32768, 2), dtype="<i2")
            block = IQBlock(
                "source-a", 1, 0, 0, 32768, 10_000_000, 144_300_000, 1,
                SampleFormat.CS16, 0, TimeDomain.UNKNOWN,
                TimestampOrigin.HOST_OBSERVATION, Discontinuity.NONE, None,
                memoryview(samples.tobytes()),
            )
            pool.process(block)
            deadline = time.monotonic() + 1.0
            while (not outputs_4m or not outputs_96k) and time.monotonic() < deadline:
                time.sleep(0.005)
            self.assertEqual(outputs_4m[-1].sample_rate_sps, 4_000_000)
            self.assertEqual(outputs_96k[-1].sample_rate_sps, 96_000)
            snapshots = {item["output_rate_sps"]: item for item in pool.snapshot()}
            self.assertEqual(snapshots[4_000_000]["parallel_workers"], 2)
            self.assertEqual(snapshots[4_000_000]["parallel_root_rate_sps"], 4_000_000)
            self.assertEqual(snapshots[96_000]["parallel_root_rate_sps"], 4_000_000)
            self.assertEqual(snapshots[96_000]["parallel_queue_drops"], 0)
        finally:
            pool.close()


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

    def test_hysteresis_and_serialization_cover_operational_fields(self):
        rule = RFRule(
            "vhf", 144_000_000, 146_000_000, 20, True, "rsp1a", "Antenna A",
            {"gain_reduction_db": 38, "lna_state": 3}, False, 1_536_000, 25_000,
        )
        restored = RFRule.from_dict(rule.to_dict())
        self.assertEqual(restored, rule)
        profiles = RFProfileSet((rule, RFRule("uhf", 146_000_000, 148_000_000, 30)))
        self.assertEqual(profiles.select(145_999_000, "rsp1a").rule_id, "vhf")
        self.assertEqual(profiles.select(146_010_000, "rsp1a", "vhf").rule_id, "vhf")
        self.assertEqual(profiles.select(146_030_000, "rsp1a", "vhf").rule_id, "uhf")


if __name__ == "__main__":
    unittest.main()
