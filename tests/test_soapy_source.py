from __future__ import annotations

import threading
import time
from types import SimpleNamespace
import unittest

import numpy as np

from sdr_bridge.model import Discontinuity, RadioConfig
from sdr_bridge.soapy_source import SoapySource


class FakeSoapyApi:
    SOAPY_SDR_RX = 1

    @staticmethod
    def Device_enumerate(_args):
        return [
            {"driver": "audio", "device_id": "0", "label": "Default audio"},
            {"driver": "miri", "miri": "0", "label": "MSi2500 alternative"},
            {"driver": "sdrplay", "serial": "0000000001", "label": "RSP1"},
            {"driver": "uhd", "serial": "B100-7", "label": "USRP B100"},
            {"driver": "sdrplay", "serial": "2001077942", "label": "RSPdx"},
        ]


class FakeRSP1ADevice:
    def __init__(self):
        self.rate = 2_000_000.0; self.bandwidth = 1_536_000.0; self.frequency = 144_300_000.0
        self.gains = {"IFGR": 40.0, "RFGR": 3.0}; self.agc = False; self.antenna = "RX"

    def listSampleRates(self, *_args): return []
    def getSampleRateRange(self, *_args): return [(2_000_000, 2_000_000, 0), (6_000_000, 6_000_000, 0)]
    def listBandwidths(self, *_args): return []
    def getBandwidthRange(self, *_args): return [(200_000, 200_000, 0), (1_536_000, 1_536_000, 0), (5_000_000, 5_000_000, 0)]
    def listAntennas(self, *_args): return ["RX"]
    def listGains(self, *_args): return ["IFGR", "RFGR"]
    def getGainRange(self, _direction, _channel, name): return (20, 59, 1) if name == "IFGR" else (0, 9, 1)
    def getGain(self, _direction, _channel, name): return self.gains[name]
    def hasGainMode(self, *_args): return True
    def getGainMode(self, *_args): return self.agc
    def getFrequencyRanges(self, *_args): return [(1_000, 2_000_000_000, 0)]
    def setSampleRate(self, _direction, _channel, value): self.rate = value
    def setBandwidth(self, _direction, _channel, value): self.bandwidth = value
    def setFrequency(self, _direction, _channel, value): self.frequency = value
    def setAntenna(self, _direction, _channel, value): self.antenna = value
    def setGainMode(self, _direction, _channel, value): self.agc = bool(value)
    def setGain(self, _direction, _channel, name, value): self.gains[name] = float(value)
    def getSampleRate(self, *_args): return self.rate
    def getBandwidth(self, *_args): return self.bandwidth
    def getFrequency(self, *_args): return self.frequency
    def getAntenna(self, *_args): return self.antenna


class FakeRSP1AApi:
    SOAPY_SDR_RX = 1
    device = FakeRSP1ADevice()
    enumerate_calls = 0

    @staticmethod
    def Device_enumerate(_args):
        FakeRSP1AApi.enumerate_calls += 1
        return [{"driver": "sdrplay", "serial": "2236027C98", "label": "SDRplay Dev0 RSP1A 2236027C98"}]

    @classmethod
    def Device(cls, _raw):
        return cls.device


class FakeStreamingDevice(FakeRSP1ADevice):
    def __init__(self):
        super().__init__()
        self.stream_format = None
        self.stream_args = None
        self.reads = 0

    def getStreamArgsInfo(self, *_args):
        return [SimpleNamespace(key="WIRE", value="sc16", options=["sc8", "sc16"])]

    def setupStream(self, _direction, fmt, channels=None, args=None):
        del channels
        self.stream_format = fmt
        self.stream_args = args
        self.reads = 0
        return object()

    def activateStream(self, _stream): return 0
    def deactivateStream(self, _stream): return 0
    def closeStream(self, _stream): return 0

    def readStream(self, _stream, buffers, _count, timeoutUs=0):
        del timeoutUs
        if self.reads:
            time.sleep(0.002)
            return SimpleNamespace(ret=-1, timeNs=0)
        self.reads += 1
        self.asserted_dtype = buffers[0].dtype
        buffers[0][:8, 0] = np.arange(8, dtype=np.int16)
        buffers[0][:8, 1] = -np.arange(8, dtype=np.int16)
        return SimpleNamespace(ret=8, timeNs=0)


class FakeStreamingApi(FakeRSP1AApi):
    SOAPY_SDR_CS8 = "CS8"
    SOAPY_SDR_CS16 = "CS16"
    SOAPY_SDR_CF32 = "CF32"
    SOAPY_SDR_TIMEOUT = -1
    SOAPY_SDR_OVERFLOW = -4
    device = FakeStreamingDevice()


class FakeOverflowDevice(FakeStreamingDevice):
    def readStream(self, _stream, buffers, _count, timeoutUs=0):
        del timeoutUs
        self.reads += 1
        if self.reads == 1:
            return SimpleNamespace(ret=-4, timeNs=0)
        if self.reads == 2:
            self.asserted_dtype = buffers[0].dtype
            buffers[0][:8, :] = 1
            return SimpleNamespace(ret=8, timeNs=0)
        time.sleep(0.002)
        return SimpleNamespace(ret=-1, timeNs=0)


class FakeFragmentedStreamingDevice(FakeStreamingDevice):
    def readStream(self, _stream, buffers, _count, timeoutUs=0):
        del timeoutUs
        if self.reads >= 4:
            time.sleep(0.002)
            return SimpleNamespace(ret=-1, timeNs=0)
        buffers[0][:8, 0] = self.reads
        buffers[0][:8, 1] = -self.reads
        self.reads += 1
        return SimpleNamespace(ret=8, timeNs=0)


class FakeSparseGenericDevice:
    """RX device with no bandwidth, antenna, AGC, or gain controls."""

    def __init__(self):
        self.rate = 2_000_000.0
        self.frequency = 5_800_000_000.0
        self.bandwidth_writes = 0

    def listSampleRates(self, *_args): return [1_000_000, 2_000_000]
    def getSampleRateRange(self, *_args): return []
    def listBandwidths(self, *_args): raise RuntimeError("NOT_SUPPORTED")
    def getBandwidthRange(self, *_args): raise RuntimeError("NOT_SUPPORTED")
    def listAntennas(self, *_args): return []
    def listGains(self, *_args): return []
    def hasGainMode(self, *_args): raise RuntimeError("NOT_SUPPORTED")
    def getFrequencyRanges(self, *_args): return [(70_000_000, 6_000_000_000, 0)]
    def setSampleRate(self, _direction, _channel, value): self.rate = value
    def setFrequency(self, _direction, _channel, value): self.frequency = value
    def setBandwidth(self, *_args): self.bandwidth_writes += 1; raise AssertionError("must not be called")
    def getSampleRate(self, *_args): return self.rate
    def getFrequency(self, *_args): return self.frequency


class FakeSparseGenericApi:
    SOAPY_SDR_RX = 1
    device = FakeSparseGenericDevice()

    @staticmethod
    def Device_enumerate(_args):
        return [{"driver": "uhd", "addr": "192.0.2.20", "type": "b100", "label": "USRP B100"}]

    @classmethod
    def Device(cls, _raw):
        return cls.device


class FakeUhdB100Device(FakeSparseGenericDevice):
    def __init__(self):
        super().__init__()
        self.rate = 2_000_000.0
        self.frequency = 16_300_000.0
        self.adc_gain = 13.0
        self.bandwidth = 2_000_000.0
        self.bandwidth_writes = 0

    def listSampleRates(self, *_args):
        return [1_000_000, 2_000_000, 4_000_000, 8_000_000, 16_000_000]

    def getSampleRateRange(self, *_args):
        return [(1_000_000, 16_000_000, 1_000_000)]

    def listBandwidths(self, *_args):
        return [2_000_000, *(500_000_000 + index * 1_000_000 for index in range(100))]

    def getBandwidthRange(self, *_args):
        return [(2_000_000, 599_000_000, 1_000_000)]

    def setBandwidth(self, _direction, _channel, value):
        self.bandwidth_writes += 1
        self.bandwidth = float(value)

    def getBandwidth(self, *_args):
        return self.bandwidth

    def getStreamArgsInfo(self, *_args):
        return [SimpleNamespace(key="WIRE", value="sc16", options=["sc8", "sc16"])]

    def listGains(self, *_args):
        return ["ADC-pga"]

    def getGainRange(self, *_args):
        return (0.0, 20.0, 1.0)

    def getGain(self, *_args):
        return self.adc_gain

    def setGain(self, _direction, _channel, name, value):
        if name == "ADC-pga":
            self.adc_gain = float(value)


class FakeUhdB100Api:
    SOAPY_SDR_RX = 1
    device = FakeUhdB100Device()
    device_args = None

    @staticmethod
    def Device_enumerate(_args):
        return [{
            "driver": "uhd",
            "type": "b100",
            "serial": "EAR15U2B1",
            "label": "EAR15U2B1",
        }]

    @classmethod
    def Device(cls, _raw):
        cls.device_args = dict(_raw)
        return cls.device


class SoapyDiscoveryTests(unittest.TestCase):
    def test_only_sdr_devices_are_exposed_with_stable_ids(self):
        source = SoapySource(api=FakeSoapyApi)
        devices = source.enumerate()
        self.assertEqual([item.backend for item in devices], [
            "soapy/sdrplay", "soapy/sdrplay", "soapy/uhd", "soapy/miri",
        ])
        self.assertEqual([item.device_id for item in devices[:3]], [
            "soapy:sdrplay:0000000001",
            "soapy:sdrplay:2001077942",
            "soapy:uhd:B100-7",
        ])
        self.assertNotIn("audio", {item.backend for item in devices})

    def test_rsp1a_range_api_and_gain_readback_are_exposed(self):
        api = FakeRSP1AApi
        api.device = FakeRSP1ADevice()
        api.enumerate_calls = 0
        source = SoapySource(api=api)
        device_id = source.enumerate()[0].device_id
        source.open(device_id)
        self.assertEqual(api.enumerate_calls, 1)
        capabilities = source.capabilities(device_id)
        self.assertEqual(capabilities.sample_rates_sps, (2_000_000, 6_000_000))
        self.assertEqual(capabilities.bandwidths_hz, (200_000, 1_536_000, 5_000_000))
        self.assertEqual(capabilities.gain_ranges, {"IFGR": (20.0, 59.0), "RFGR": (0.0, 9.0)})
        self.assertEqual(capabilities.gain_values, {"IFGR": 40.0, "RFGR": 3.0})
        effective = source.configure(RadioConfig(gains={"IFGR": 35, "RFGR": 2}, antenna="RX"))
        self.assertEqual(effective.gains, {"IFGR": 35.0, "RFGR": 2.0})
        self.assertEqual(effective.gain_reduction_db, 35)

    def test_generic_device_without_optional_controls_remains_usable(self):
        api = FakeSparseGenericApi
        api.device = FakeSparseGenericDevice()
        source = SoapySource(api=api)
        first_id = source.enumerate()[0].device_id
        second_id = source.enumerate()[0].device_id
        self.assertEqual(first_id, second_id)
        self.assertTrue(first_id.startswith("soapy:uhd:"))
        source.open(first_id)
        capabilities = source.capabilities(first_id)
        self.assertEqual(capabilities.frequency_ranges_hz, ((70_000_000, 6_000_000_000),))
        self.assertEqual(capabilities.bandwidths_hz, ())
        self.assertFalse(capabilities.agc_available)
        effective = source.configure(RadioConfig(
            center_frequency_hz=5_800_000_000,
            sample_rate_sps=2_000_000,
            bandwidth_hz=1_536_000,
        ))
        self.assertEqual(effective.center_frequency_hz, 5_800_000_000)
        self.assertEqual(api.device.bandwidth_writes, 0)

    def test_uhd_capabilities_are_exposed_without_model_specific_limits(self):
        api = FakeUhdB100Api
        api.device = FakeUhdB100Device()
        source = SoapySource(api=api)
        device_id = source.enumerate()[0].device_id
        source.open(device_id)

        self.assertEqual(api.device_args["num_recv_frames"], "1024")
        capabilities = source.capabilities(device_id)
        self.assertEqual(capabilities.sample_rates_sps, (1_000_000, 2_000_000, 4_000_000, 8_000_000, 16_000_000))
        self.assertEqual(capabilities.sample_rate_ranges_sps, ((1_000_000.0, 16_000_000.0, 1_000_000.0),))
        self.assertIn(500_000_000, capabilities.bandwidths_hz)
        self.assertEqual(capabilities.wire_formats, ("sc8", "sc16"))
        self.assertEqual(capabilities.wire_format_default, "sc16")
        self.assertEqual(capabilities.gain_ranges, {"ADC-pga": (0.0, 20.0)})

        automatic = source.configure(RadioConfig(
            center_frequency_hz=16_300_000,
            sample_rate_sps=16_000_000,
            bandwidth_hz=500_000_000,
        ))
        self.assertIsNone(automatic.wire_format)
        self.assertEqual(source._resolved_wire_format, "sc8")

        source.configure(RadioConfig(
            center_frequency_hz=16_300_000,
            sample_rate_sps=8_000_000,
            bandwidth_hz=500_000_000,
        ))
        self.assertEqual(source._resolved_wire_format, "sc16")

        effective = source.configure(RadioConfig(
            center_frequency_hz=16_300_000,
            sample_rate_sps=16_000_000,
            bandwidth_hz=500_000_000,
            gains={"ADC-pga": 18},
            wire_format="SC8",
        ))
        self.assertEqual(effective.sample_rate_sps, 16_000_000)
        self.assertEqual(effective.bandwidth_hz, 500_000_000)
        self.assertEqual(effective.wire_format, "sc8")
        self.assertEqual(effective.gains["ADC-pga"], 18.0)
        self.assertEqual(api.device.adc_gain, 18.0)
        self.assertEqual(api.device.bandwidth_writes, 3)

        with self.assertRaisesRegex(ValueError, "unsupported IQ transport format"):
            source.configure(RadioConfig(wire_format="sc12"))

    def test_sc8_wire_keeps_source_callback_on_raw_sc8(self):
        api = FakeStreamingApi
        api.device = FakeStreamingDevice()
        source = SoapySource(block_samples=8, api=api)
        device_id = source.enumerate()[0].device_id
        source.open(device_id)
        source.configure(RadioConfig(wire_format="sc8"))
        received = []
        ready = threading.Event()

        def on_block(chunk):
            received.append((chunk.payload_format, np.frombuffer(chunk.payload, dtype="i1").copy()))
            ready.set()

        source.start(on_block)
        try:
            self.assertTrue(ready.wait(1.0))
        finally:
            source.stop()
        self.assertEqual(api.device.stream_format, "CS8")
        self.assertEqual(api.device.stream_args, {"WIRE": "sc8"})
        self.assertEqual(api.device.asserted_dtype, np.dtype("i1"))
        self.assertEqual(received[0][0], "CS8")
        np.testing.assert_array_equal(
            received[0][1].reshape(-1, 2)[:, 0],
            np.arange(8, dtype=np.int8),
        )
        self.assertEqual(source.diagnostics()["host_stream_format"], "CS8")

    def test_small_driver_reads_are_coalesced_into_bridge_blocks(self):
        api = FakeStreamingApi
        api.device = FakeFragmentedStreamingDevice()
        source = SoapySource(block_samples=32, api=api)
        device_id = source.enumerate()[0].device_id
        source.open(device_id)
        source.configure(RadioConfig())
        received = []
        ready = threading.Event()

        def on_block(chunk):
            received.append(chunk)
            ready.set()

        source.start(on_block)
        try:
            self.assertTrue(ready.wait(1.0))
        finally:
            source.stop()
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].sample_count, 32)
        values = np.frombuffer(received[0].payload, dtype="<i2").reshape(-1, 2)
        np.testing.assert_array_equal(values[:, 0], np.repeat(np.arange(4, dtype=np.int16), 8))
        diagnostics = source.diagnostics()
        self.assertEqual(diagnostics["read_calls"], 4)
        self.assertEqual(diagnostics["short_reads"], 4)
        self.assertEqual(diagnostics["minimum_read_samples"], 8)
        self.assertEqual(diagnostics["maximum_read_samples"], 8)

    def test_rx_overflow_is_reported_as_recoverable_source_loss(self):
        api = FakeStreamingApi
        api.device = FakeOverflowDevice()
        source = SoapySource(block_samples=8, api=api)
        device_id = source.enumerate()[0].device_id
        source.open(device_id)
        source.configure(RadioConfig())
        received = []
        errors = []
        ready = threading.Event()

        def on_block(chunk):
            received.append(chunk)
            ready.set()

        source.start(on_block, errors.append)
        try:
            self.assertTrue(ready.wait(1.0))
        finally:
            source.stop()
        self.assertFalse(errors)
        self.assertEqual(received[0].discontinuity, Discontinuity.SOURCE_LOSS)
        self.assertIsNone(received[0].lost_samples)
        self.assertEqual(received[0].first_sample_index, 0)

    def test_repeated_rate_and_wire_rebuilds_leave_no_live_stream(self):
        api = FakeStreamingApi
        api.device = FakeStreamingDevice()
        source = SoapySource(block_samples=8, api=api)
        device_id = source.enumerate()[0].device_id
        source.open(device_id)
        for index in range(25):
            source.configure(RadioConfig(
                sample_rate_sps=2_000_000 if index % 2 == 0 else 6_000_000,
                bandwidth_hz=1_536_000 if index % 2 == 0 else 5_000_000,
                wire_format="sc16" if index % 2 == 0 else "sc8",
            ))
            source.start(lambda _chunk: None)
            time.sleep(0.003)
            source.stop()
            self.assertIsNone(source._thread)
            self.assertIsNone(source._stream)
        source.close()


if __name__ == "__main__":
    unittest.main()
