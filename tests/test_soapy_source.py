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
        self.reads = 0

    def setupStream(self, _direction, fmt):
        self.stream_format = fmt
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

    def test_stream_requests_direct_cs16_and_skips_python_cf32_conversion(self):
        api = FakeStreamingApi
        api.device = FakeStreamingDevice()
        source = SoapySource(block_samples=32, api=api)
        device_id = source.enumerate()[0].device_id
        source.open(device_id)
        source.configure(RadioConfig())
        received = []
        ready = threading.Event()

        def on_block(chunk):
            received.append(np.frombuffer(chunk.payload, dtype="<i2").copy())
            ready.set()

        source.start(on_block)
        try:
            self.assertTrue(ready.wait(1.0))
        finally:
            source.stop()
        self.assertEqual(api.device.stream_format, "CS16")
        self.assertEqual(api.device.asserted_dtype, np.dtype("<i2"))
        np.testing.assert_array_equal(received[0].reshape(-1, 2)[:, 0], np.arange(8, dtype=np.int16))

    def test_rx_overflow_is_reported_as_recoverable_source_loss(self):
        api = FakeStreamingApi
        api.device = FakeOverflowDevice()
        source = SoapySource(block_samples=32, api=api)
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


if __name__ == "__main__":
    unittest.main()
