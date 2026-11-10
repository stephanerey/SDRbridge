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
- SDRplay **IFGR/RFGR** are gain reductions. The GUI reverses their visual
  direction so moving right behaves like increasing gain.
- **RF profiles** automatically apply antenna, gain, AGC and bandwidth by
  frequency range.

## Losses and performance

**Total losses** includes source, DSP and UDP losses. A rising value means that
useful samples or blocks could not be processed. **SDRbridge CPU** is displayed
as logical cores used, not total-machine percentage.

If losses appear, reduce very large FFTs, use Waterfall only, lower an output
rate, remove unused clients, or moderately increase that destination's queue.
Use **Diagnostics → Export report ZIP** and attach the archive to a bug report.

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

The 0.6.0 package includes only the `SoapySDRPlay3` hardware module. SDRplay
receivers are therefore the only hardware supported out of the box by this
installer. RTL-SDR, USRP/UHD, Airspy, HackRF or LimeSDR requires a compatible
Soapy module to be added and qualified inside SDRbridge's private runtime;
modules from the system-wide PothosSDR installation are not loaded.

## Support, license and donations

SDRbridge is licensed under GNU GPL version 3 or later and comes without any
warranty. Authors: Stéphane REY F1TJJ and Philippe Borghini F5JWF. Source code
and issue tracking: https://github.com/stephanerey/SDRbridge.
