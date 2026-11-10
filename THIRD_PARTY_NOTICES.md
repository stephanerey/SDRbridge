# Third-party notices

SDRbridge is distributed under `GPL-3.0-or-later`. Its executable distribution
contains or uses the following third-party components. Each component remains
under its own license.

| Component | Version used for 0.6.0 | License | Project |
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
| SoapySDR | 0.9.0, commit `cf0c0eb5279aa202d5b3a48aee423294b10244eb` | BSL-1.0 | https://github.com/pothosware/SoapySDR |
| SoapySDRPlay3 | 0.5.2, commit `48bd8b41072534018de1d74deb3dea5874d9e0e0` | MIT | https://github.com/pothosware/SoapySDRPlay3 |
| PyInstaller bootloader | 6.22.3 | GPL-2.0-or-later with bootloader exception | https://pyinstaller.org/ |
| Microsoft Visual C++ Runtime | 14.51 | Microsoft distributable code | https://aka.ms/vs/18/redistribution |

The official SDRplay API, service and hardware driver are installed separately
by the user. SDRbridge does not redistribute `sdrplay_api.dll`. SDRplay names
and marks belong to SDRplay Limited; their presence does not imply endorsement.

The release package contains verbatim license files for the components it
bundles. Complete dependency notices shipped by NumPy, SciPy and Qt are also
preserved in the application distribution.
