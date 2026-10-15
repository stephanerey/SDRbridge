from __future__ import annotations

import unittest

from sdr_bridge.soapy_source import SoapySource


class FakeSoapyApi:
    @staticmethod
    def Device_enumerate(_args):
        return [
            {"driver": "audio", "device_id": "0", "label": "Default audio"},
            {"driver": "miri", "miri": "0", "label": "MSi2500 alternative"},
            {"driver": "sdrplay", "serial": "0000000001", "label": "RSP1"},
            {"driver": "uhd", "serial": "B100-7", "label": "USRP B100"},
            {"driver": "sdrplay", "serial": "2001077942", "label": "RSPdx"},
        ]


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


if __name__ == "__main__":
    unittest.main()
