# Third-party notices

SDRbridge is distributed under `GPL-3.0-or-later`. Its executable distribution
contains or uses the following third-party components. Each component remains
under its own license.

| Component | Version used by the development build | License | Project |
|---|---:|---|---|
| Python | 3.12 | PSF License | https://www.python.org/ |
| PyQt5 | 5.15.11 | GPL-3.0 or commercial | https://www.riverbankcomputing.com/software/pyqt/ |
| Qt | 5.15.2 | LGPL-3.0 / GPL-2.0 / GPL-3.0 or commercial | https://www.qt.io/ |
| NumPy | 2.5.4 | BSD-3-Clause and bundled notices | https://numpy.org/ |
| SciPy | 1.18.1 | BSD-3-Clause and bundled notices | https://scipy.org/ |
| pyqtgraph | 0.14.0 | MIT | https://www.pyqtgraph.org/ |
| python-zeroconf | 0.151.5 | LGPL-2.1-or-later | https://github.com/python-zeroconf/python-zeroconf |
| PyYAML | 6.0.3 | MIT | https://pyyaml.org/ |
| jsonschema | 4.26.0 | MIT | https://github.com/python-jsonschema/jsonschema |
| SoapySDR | 0.8.1 Pothos VC16 runtime; SDK commit `1cf5a539a21414ff509ff7d0eedfc5fa8edb90c6` | BSL-1.0 | https://github.com/pothosware/SoapySDR |
| SoapySDRPlay3 | 0.5.2, commit `48bd8b41072534018de1d74deb3dea5874d9e0e0` | MIT | https://github.com/pothosware/SoapySDRPlay3 |
| SoapyRTLSDR | commit `5b544e3d3a7ae97952742f42f8bb110fe62c3cd8` | MIT | https://github.com/pothosware/SoapyRTLSDR |
| SoapyAirspy | commit `9a906cac218bf07a7acd31efa1f2954c3a44ea4b` | MIT | https://github.com/pothosware/SoapyAirspy |
| SoapyAirspyHF | commit `0b3daf0b47c3c1d0857c873bb184f6a86a37333c` | MIT | https://github.com/pothosware/SoapyAirspyHF |
| SoapyLMS7 (LimeSuite) | commit `3c53defaa338060d7d70481c68fedb6aebb41e7a` | Apache-2.0 | https://github.com/myriadrf/LimeSuite |
| SoapyPlutoSDR | 0.2.4, commit `0046115838a3c024e5f5869701c45a8d85060d6e` | LGPL-2.1 | https://github.com/pothosware/SoapyPlutoSDR |
| SoapyUHD | 0.4.2, commit `d6f7feaf016e1559ea479007196def1cc55a463c` | GPL-3.0 | https://github.com/pothosware/SoapyUHD |
| Boost headers/import libraries | 1.75.0, MSVC 14.2 x64 | BSL-1.0 | https://www.boost.org/ |
| libairspy | 1.0.10 | BSD-3-Clause | https://github.com/airspy/airspyone_host |
| libairspyhf | 1.8.1 | BSD-3-Clause | https://github.com/airspy/airspyhf |
| rtl-sdr | PothosSDR binary runtime | GPL-2.0 | https://osmocom.org/projects/rtl-sdr |
| LimeSuite | PothosSDR binary runtime | Apache-2.0 | https://github.com/myriadrf/LimeSuite |
| libiio | PothosSDR binary runtime | LGPL-2.1 | https://github.com/analogdevicesinc/libiio |
| libad9361 | PothosSDR binary runtime | LGPL-2.1 | https://github.com/analogdevicesinc/libad9361-iio |
| libusb | PothosSDR binary runtime | LGPL-2.1 | https://github.com/libusb/libusb |
| UHD | 4.0 PothosSDR binary runtime | GPL-3.0-or-later | https://github.com/EttusResearch/uhd |
| pthreads-win32 | PothosSDR binary runtime | LGPL-2.1 | https://sourceware.org/pthreads-win32/ |
| PyInstaller bootloader | 6.22.3 | GPL-2.0-or-later with bootloader exception | https://pyinstaller.org/ |
| Microsoft Visual C++ Runtime | 14.51 | Microsoft distributable code | https://aka.ms/vs/18/redistribution |

The official SDRplay API, service and hardware driver are installed separately
by the user. SDRbridge does not redistribute `sdrplay_api.dll`. SDRplay names
and marks belong to SDRplay Limited; their presence does not imply endorsement.

The development installer bundles the vendor runtime DLLs required by the
additional Soapy modules (RTL-SDR, Airspy, Airspy HF+, LimeSuite,
libiio/libad9361, libusb and UHD). Their complete license texts are preserved
in the installed `licenses` directory. Hardware-specific Windows drivers and
UHD firmware/FPGA images are not bundled.

The release package contains verbatim license files for the components it
bundles. Complete dependency notices shipped by NumPy, SciPy and Qt are also
preserved in the application distribution.
