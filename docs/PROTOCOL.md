# SDR_Bridge local and UDP protocol

## Local control

The control socket listens only on `127.0.0.1:47631`. Messages are newline-delimited UTF-8 JSON. Client adapters may use `register`, `heartbeat`, and `status`. Only the GUI-held control token may use `set_config`.

Registration returns the Windows shared-memory name and ring geometry. Samples are signed 16-bit little-endian pairs in `I,Q,I,Q` order.

## Shared ring

The global header contains magic `SDBR`, protocol version, slot count, payload size, slot-header size, and latest sequence. Each slot contains sequence, monotonic timestamp in nanoseconds, configuration revision, sample count, commit sequence, then the I/Q payload. A matching commit sequence means the slot is complete.

Readers maintain independent cursors. If a cursor is older than `latest_sequence - slot_count + 1`, the reader counts the skipped blocks and resumes at the oldest retained block.

## Experimental UDP/LAN

UDP packets use magic `SDBU`, version 1, S16LE format ID 1, block sequence, timestamp, configuration revision, fragment index and fragment count. There is no retransmission in the real-time profile. This is an SDR_Bridge protocol; application-specific QMAP/Linrad compatibility profiles still require validation.

