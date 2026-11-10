# SDRbridge 0.6.0

SDRbridge 0.6.0 distributes one RX IQ source to several radio applications at
the same time. It is strictly receive-only: client applications cannot take
control of the radio hardware.

## Highlights

- simultaneous operation verified with SDR++, HDSDR, SDRuno and QMAP;
- independent, genuinely filtered output rates for every UDP destination;
- native QMAP/Linrad stream at 96 kS/s;
- HDSDR and SDR++ IQ WAV/RF64 replay selected directly from the GUI;
- SigMF, SDR++ WAV and HDSDR WAV recording through a native Save As dialog;
- persistent RF profiles for antenna, AGC, gains and hardware bandwidth;
- bilingual French/English dark GUI with Spectrum, Waterfall, Split and compact
  views;
- multicore DSP pipeline qualified at a 10 MS/s source rate with simultaneous
  4 MS/s and 96 kS/s outputs and no reported loss;
- self-contained Python, Qt and private SoapySDR runtime.

## Hardware and client scope

The 0.6.0 installer includes only the `SoapySDRPlay3` hardware module. SDRplay
receivers are therefore the only SDR hardware supported out of the box. The
official SDRplay API/driver 3.15 must already be installed.

The generic SoapySDR backend can support RTL-SDR, USRP/UHD, Airspy, HackRF,
LimeSDR and other devices after their matching module has been added to and
qualified with SDRbridge's private runtime. System-wide PothosSDR modules are
not loaded by this release.

Certified client paths are SDR++ 1.3.x through SDBU v2, QMAP 0.6 through its
Linrad input, and HDSDR 2.81a or SDRuno 1.42.1710 through the supplied Win32
ExtIO adapter. ANTRACK uses the supplied local compatibility connector.

## Verification

- 90/90 automated tests passed;
- RSP1A qualification passed at 10 MS/s with 4 MS/s and QMAP 96 kS/s outputs;
- isolated silent install, private Soapy runtime probe and uninstall passed;
- no `sdrplay_api.dll` is redistributed by SDRbridge.

Installer SHA-256:
`82DF0435C88B200D3E59A654EDA3A936F075921C2BC18F7CDE068B51F24310F7`

The installer is not digitally signed. Windows SmartScreen may therefore show
a warning. See the repository README and the bilingual in-application help for
installation and client configuration details.
