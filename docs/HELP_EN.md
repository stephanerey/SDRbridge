# SDRbridge 0.6 Help

SDRbridge receives I/Q samples from one SDR or recording and distributes them
to several applications and recorders at the same time. Every UDP destination
can use its own effective sample rate.

## Quick start

1. For an SDRplay receiver, first install the official SDRplay API and driver
   3.15. Restart Windows if requested by that installer.
2. Start SDRbridge. Python, Qt and SoapySDR are already included.
3. On **Radio**, select the receiver and IQ sample rate. Keep bandwidth on
   **Auto**.
4. Press **Acquisition**. The button is amber while hardware opens, green only
   when samples are flowing, and grey when stopped.
5. Add the required destinations in **Clients & Streams**.

## Common client settings

| Client | Typical destination | Transport | Rate |
|---|---|---|---:|
| SDR++ | `127.0.0.1:7355` | SDR++ raw CS16 or SDBU v2 | client-specific |
| QMAP 0.6 | `127.0.0.1:50004` | QMAP/Linrad | fixed 96 kS/s |
| Second SDR++ | `127.0.0.1:7357` | SDR++ raw CS16 or SDBU v2 | e.g. 192 kS/s |

Destinations at the same rate share one DSP pipeline. A lower-rate destination
receives a genuinely filtered and decimated stream, not merely fewer packets.

## IQ files and capture

Choose **IQ file…** from the source list. SDRbridge reads stereo I/Q WAV or
RF64 recordings from HDSDR and SDR++, plus SigMF captures. File-derived radio
parameters are displayed read-only. Enable **Loop IQ file** to restart at EOF.

The **Captures** page writes SigMF 1.2.6, SDR++ stereo int16 WAV, or HDSDR
stereo int16 WAV. The default Save As location is SDRbridge's `Captures` folder.

## RF controls

- **Sample rate** is the width of the IQ stream produced by the SDR.
- **Bandwidth** is the analogue/IF hardware filter exposed by the device. Auto
  chooses the available value closest to the requested sample rate.
- **IQ transport** appears only when the Soapy driver advertises native wire
  formats. It changes the SDR-to-computer link, not the CS16 client streams.
  For example, a B100 can use SC16 up to 8 MS/s or SC8 up to 16 MS/s.
  Auto displays its effective choice and favours precision while staying
  within the throughput envelope advertised by the driver.
- Every listed sample rate, bandwidth, antenna and gain comes from the selected
  receiver's Soapy capabilities; SDRbridge contains no receiver-model table.
- SDRplay **IFGR/RFGR** are gain reductions. The GUI reverses their visual
  direction so moving right behaves like increasing gain.
- **RF profiles** automatically apply antenna, gain, AGC and bandwidth by
  frequency range.

## Losses and performance

**Total losses** combines several counters. **Source** losses are reported by
the receiver or its driver before SDRbridge processing. **Queue**, **DSP** and
**profile** losses occur inside the processing path. **UDP** losses concern a
destination queue or network output. The diagnostic report keeps these
categories separate. **SDRbridge CPU** is displayed as logical cores used, not
total-machine percentage.

For internal processing losses, reduce very large FFTs, use Waterfall only,
lower an output rate or remove unused clients. For UDP losses, moderately
increase that destination's queue and check the network. For source losses,
check the receiver, its driver, connection and effective sample rate. Use
**Diagnostics → Export report ZIP** and attach the archive to a bug report.

## HDSDR and local ExtIO clients

HDSDR does not use UDP destinations such as `7355` or `7356`. The ExtIO first
connects to the local control endpoint at `127.0.0.1:47631`, then reads the
SDBR v2 shared-memory ring. There is no IQ port to configure in HDSDR.

The ExtIO reads the master ring at the full source rate and does not select a
per-client decimated profile. A 10 MS/s source is therefore delivered to
HDSDR at 10 MS/s. Each HDSDR instance appears under **Active consumers** and
contributes to **Logical IQ rate**, but not to **Useful UDP rate** or measured
network throughput. Multiple instances share the ring that SDRbridge writes
once; each instance still incurs its own copy, FFT, waterfall and demodulation
CPU cost.

HDSDR 2.81a and SDRuno 1.42.1710 are certified ExtIO hosts. For SDRuno, copy
the DLL to `C:\Program Files (x86)\SDRplay\SDRuno`, then run
`SDRuno.EXTIO.exe`, not `SDRuno.exe`. **In SR** must display the source rate.
Other Win32 ExtIO hosts are not guaranteed without an explicit test.

## Requirements

- Windows 10 or Windows 11 x64;
- SDRplay: official API/driver 3.15;
- SDR++: x64 installation plus the module supplied with SDRbridge;
- HDSDR: 32-bit installation plus the supplied ExtIO;
- QMAP and ANTRACK: separate installations with no shared Soapy runtime.

SDRbridge includes its own SoapySDR runtime. Do not copy its DLLs into
PothosSDR, ANTRACK or SDR++.

Version 0.7.0 includes private ABI 0.8 modules for SDRplay, RTL-SDR, Airspy R2,
Airspy HF+, LimeSDR, ADALM-Pluto and USRP/UHD. Hardware controls are shown only
when the selected module reports them.

Before starting SDRbridge, install and validate the manufacturer's driver,
API, firmware and hardware images. SDRbridge does not install or modify that
vendor stack. Modules from the system-wide PothosSDR installation are not
loaded into SDRbridge's private runtime.

## LAN UDP destinations

Remote UDP destinations are disabled by default. In **Settings**, enable
**Allow LAN UDP destinations** before adding a non-loopback address. This
permission is saved immediately and does not expose RF control on the network.
For LAN traffic, use 1200-byte datagrams; the editor automatically replaces the
8192-byte loopback default when a remote endpoint is entered. The receiver must
bind its LAN address or `0.0.0.0`, and its firewall must allow the selected UDP
port.

## Support, license and donations

SDRbridge is licensed under GNU GPL version 3 or later and comes without any
warranty. Authors: Stéphane REY F1TJJ and Philippe Borghini F5JWF. Source code
and issue tracking: https://github.com/stephanerey/SDRbridge.

The software was developed with AI assistance under human direction, review,
hardware testing, and release validation, using
[Auroramind](https://www.auroramind.fr/)'s
[SR Method 4.1](https://github.com/syl2042/Aurora_SR_method_codex_pack).
