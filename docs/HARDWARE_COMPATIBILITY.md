[Documentation française](HARDWARE_COMPATIBILITY_FR.md)

# Hardware validation matrix

SDRbridge is capability-driven: it does not identify a receiver model to
invent controls or rate limits. The table below records configurations that
have actually been exercised. It is evidence of testing, not a hard-coded
compatibility list.

The user must install the manufacturer's driver, API, firmware and hardware
images first. The receiver must operate correctly through its SoapySDR module
before SDRbridge can use it.

“Maximum tested IQ rate” means the highest source sample rate exercised during
the recorded validation. It is not necessarily the hardware's absolute limit
and is distinct from the analogue RF frontend bandwidth.

| Receiver | Soapy backend | Maximum tested IQ rate | Source resolution / transport | Validation status |
|---|---|---:|---|---|
| SDRplay RSP1A | `sdrplay` | 10 MS/s | CS16 host samples | RX, dynamic controls and simultaneous 4 MS/s plus QMAP outputs validated on Windows 11 |
| SDRplay RSPdx | native SDRplay and `sdrplay` | 2 MS/s | CS16 host samples | RX and hardware controls validated on Windows |
| RSP1-compatible MSI Panadapter | `sdrplay` | Not recorded | CS16 host samples | RX validated alone and concurrently with an RSPdx |
| Ettus USRP B100 | `uhd` | 16 MS/s | SC8 over the device link, CS8 host hand-off, CS16 bridge streams | Detection, RX, rate and transport selection validated on Windows 11 |
| Airspy R2 | `airspy` | Pending | Pending | Real-hardware validation assigned |
| Airspy HF+ | `airspyhf` | Pending | Pending | Real-hardware validation assigned |
| RTL-SDR E4000 | `rtlsdr` | Pending | Pending | Real-hardware validation assigned |
| RTL-SDR R820T | `rtlsdr` | Pending | Pending | Real-hardware validation assigned |
| LimeSDR Mini | `lime` | Pending | Pending | Real-hardware validation assigned |
| ADALM-Pluto | `plutosdr` | Pending | Pending | Real-hardware validation assigned |

For a new result, record the exact receiver, Windows and driver versions,
Soapy backend, highest tested source rate, effective IQ transport/resolution,
client outputs, test duration and diagnostic report. Do not mark a receiver as
validated merely because its Soapy factory loads.

Use the [generic Soapy qualification procedure](verification/GENERIC_SOAPY_VALIDATION.md)
for repeatable tests.
