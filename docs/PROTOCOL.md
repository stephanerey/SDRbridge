# SDR_Bridge local and UDP protocol

## Local control

The control socket listens only on `127.0.0.1:47631`. Messages are newline-delimited UTF-8 JSON. Client adapters may use `register`, `heartbeat`, and `status`. Only the GUI-held control token may use `set_config`.

Registration returns the Windows shared-memory name and ring geometry. Samples are signed 16-bit little-endian pairs in `I,Q,I,Q` order.

## Shared ring

The global header contains magic `SDBR`, protocol version, slot count, payload size, slot-header size, and latest sequence. Each slot contains sequence, monotonic timestamp in nanoseconds, configuration revision, sample count, commit sequence, then the I/Q payload. A matching commit sequence means the slot is complete.

Readers maintain independent cursors. If a cursor is older than `latest_sequence - slot_count + 1`, the reader counts the skipped blocks and resumes at the oldest retained block.

## SDBU v2

UDP packets use magic `SDBU`, version 2 and a 72-byte big-endian header followed by CS16 or CF32 little-endian samples. There is no retransmission in the real-time profile.

## QMAP / Linrad UDP

Transport name: `qmap_linrad`. SDRbridge first uses the immutable `qmap-linrad-96k` CS16 profile to resample the selected source to exactly 96,000 complex samples/s. Framing is post-DSP and therefore does not alter SDBU or SDR++ destinations.

Every little-endian datagram is exactly 1416 bytes: `double center_frequency_mhz`, `int32 milliseconds`, `float user_frequency`, `int32 sample_pointer`, `uint16 block_sequence`, `int8 receiver_count=1`, `char sideband`, then 348 interleaved `int16 I,Q` pairs. Before framing, samples are mapped with `(-1)^n * conj(I+jQ)` to match QMAP's spectral convention. Partial packets are discarded across an epoch, frequency, rate or discontinuity boundary. Default QMAP port: UDP `50004` on loopback.

