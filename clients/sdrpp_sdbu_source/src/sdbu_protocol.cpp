#include "sdbu_protocol.h"

#include <cstring>
#include <limits>

namespace sdbu {
namespace {

std::uint16_t readBe16(const std::uint8_t* p) {
    return static_cast<std::uint16_t>((static_cast<std::uint16_t>(p[0]) << 8) |
                                      static_cast<std::uint16_t>(p[1]));
}

std::uint32_t readBe32(const std::uint8_t* p) {
    return (static_cast<std::uint32_t>(p[0]) << 24) |
           (static_cast<std::uint32_t>(p[1]) << 16) |
           (static_cast<std::uint32_t>(p[2]) << 8) |
           static_cast<std::uint32_t>(p[3]);
}

std::uint64_t readBe64(const std::uint8_t* p) {
    return (static_cast<std::uint64_t>(readBe32(p)) << 32) |
           static_cast<std::uint64_t>(readBe32(p + 4));
}

bool fail(std::string& error, const char* message) {
    error = message;
    return false;
}

} // namespace

bool parseDatagram(const std::uint8_t* data, std::size_t size,
                   DatagramView& out, std::string& error) {
    error.clear();
    if (!data || size < HEADER_BYTES) {
        return fail(error, "truncated SDBU datagram");
    }
    if (std::memcmp(data, "SDBU", 4) != 0) {
        return fail(error, "invalid SDBU magic");
    }
    if (data[4] != VERSION) {
        return fail(error, "unsupported SDBU version");
    }
    if (data[5] != static_cast<std::uint8_t>(SampleFormat::CS16) &&
        data[5] != static_cast<std::uint8_t>(SampleFormat::CF32)) {
        return fail(error, "unsupported SDBU sample format");
    }

    const auto flags = readBe16(data + 6);
    const auto headerBytes = readBe16(data + 8);
    const auto timeDomain = data[10];
    const auto reserved8 = data[11];
    const auto streamId = readBe32(data + 12);
    const auto epoch = readBe64(data + 16);
    const auto sequence = readBe64(data + 24);
    const auto firstIndex = readBe64(data + 32);
    const auto timestamp = readBe64(data + 40);
    const auto revision = readBe32(data + 48);
    const auto rate = readBe32(data + 52);
    const auto frequency = readBe64(data + 56);
    const auto count = readBe32(data + 64);
    const auto reserved32 = readBe32(data + 68);

    if (headerBytes != HEADER_BYTES) {
        return fail(error, "invalid SDBU header length");
    }
    if ((flags & ~KNOWN_FLAGS) != 0) {
        return fail(error, "unknown SDBU flags");
    }
    if (reserved8 != 0 || reserved32 != 0) {
        return fail(error, "reserved SDBU field is non-zero");
    }
    if (streamId == 0 || revision == 0 || rate == 0 || count == 0) {
        return fail(error, "invalid zero-valued SDBU field");
    }
    if (sequence == std::numeric_limits<std::uint64_t>::max() ||
        firstIndex > std::numeric_limits<std::uint64_t>::max() - count) {
        return fail(error, "SDBU counter would wrap");
    }
    if (timeDomain > 4) {
        return fail(error, "unknown SDBU time domain");
    }
    const bool timeValid = (flags & FLAG_TIME_VALID) != 0;
    if (timeValid && timeDomain == 0) {
        return fail(error, "valid SDBU time has unknown domain");
    }
    if (!timeValid && (timeDomain != 0 || timestamp != 0)) {
        return fail(error, "invalid SDBU time metadata");
    }
    if ((flags & FLAG_HARDWARE_ORIGIN) != 0 && !timeValid) {
        return fail(error, "SDBU hardware origin requires valid time");
    }

    const auto format = static_cast<SampleFormat>(data[5]);
    const std::size_t bytesPerIq = format == SampleFormat::CS16 ? 4u : 8u;
    if (size < HEADER_BYTES || count > (size - HEADER_BYTES) / bytesPerIq) {
        return fail(error, "SDBU payload length overflow");
    }
    const std::size_t payloadBytes = static_cast<std::size_t>(count) * bytesPerIq;
    if (size != HEADER_BYTES + payloadBytes) {
        return fail(error, "SDBU datagram length mismatch");
    }

    out.format = format;
    out.flags = flags;
    out.timeDomain = timeDomain;
    out.wireStreamId = streamId;
    out.epoch = epoch;
    out.packetSequence = sequence;
    out.firstSampleIndex = firstIndex;
    out.timestampNs = timestamp;
    out.configRevision = revision;
    out.sampleRateSps = rate;
    out.centerFrequencyHz = frequency;
    out.sampleCount = count;
    out.payload = data + HEADER_BYTES;
    out.payloadBytes = payloadBytes;
    return true;
}

ContinuityResult ContinuityTracker::observe(const DatagramView& packet) {
    if (!initialized_) {
        initialized_ = true;
        streamId_ = packet.wireStreamId;
        epoch_ = packet.epoch;
        nextSequence_ = packet.packetSequence + 1;
        nextSampleIndex_ = packet.firstSampleIndex + packet.sampleCount;
        return ContinuityResult::First;
    }

    if (packet.wireStreamId != streamId_ || packet.epoch != epoch_) {
        // The first packet of every output/epoch is sequence zero and carries
        // DISCONTINUITY. Requiring both prevents a late datagram from a retired
        // epoch from switching the receiver backwards.
        if (packet.packetSequence != 0 ||
            (packet.flags & FLAG_DISCONTINUITY) == 0) {
            return ContinuityResult::OldOrDuplicate;
        }
        streamId_ = packet.wireStreamId;
        epoch_ = packet.epoch;
        nextSequence_ = packet.packetSequence + 1;
        nextSampleIndex_ = packet.firstSampleIndex + packet.sampleCount;
        return ContinuityResult::NewEpoch;
    }

    if (packet.packetSequence < nextSequence_) {
        return ContinuityResult::OldOrDuplicate;
    }

    const bool gap = packet.packetSequence != nextSequence_ ||
                     packet.firstSampleIndex != nextSampleIndex_ ||
                     (packet.flags & FLAG_DISCONTINUITY) != 0;
    nextSequence_ = packet.packetSequence + 1;
    nextSampleIndex_ = packet.firstSampleIndex + packet.sampleCount;
    return gap ? ContinuityResult::Gap : ContinuityResult::Continuous;
}

void ContinuityTracker::reset() {
    initialized_ = false;
    streamId_ = 0;
    epoch_ = 0;
    nextSequence_ = 0;
    nextSampleIndex_ = 0;
}

} // namespace sdbu

