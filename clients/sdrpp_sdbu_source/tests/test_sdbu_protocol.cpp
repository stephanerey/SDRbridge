#include "sdbu_protocol.h"

#include <array>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>

namespace {

void putBe16(std::vector<std::uint8_t>& out, std::size_t at, std::uint16_t v) {
    out[at] = static_cast<std::uint8_t>(v >> 8);
    out[at + 1] = static_cast<std::uint8_t>(v);
}

void putBe32(std::vector<std::uint8_t>& out, std::size_t at, std::uint32_t v) {
    out[at] = static_cast<std::uint8_t>(v >> 24);
    out[at + 1] = static_cast<std::uint8_t>(v >> 16);
    out[at + 2] = static_cast<std::uint8_t>(v >> 8);
    out[at + 3] = static_cast<std::uint8_t>(v);
}

void putBe64(std::vector<std::uint8_t>& out, std::size_t at, std::uint64_t v) {
    putBe32(out, at, static_cast<std::uint32_t>(v >> 32));
    putBe32(out, at + 4, static_cast<std::uint32_t>(v));
}

std::vector<std::uint8_t> packet(std::uint64_t sequence = 0,
                                 std::uint64_t firstIndex = 5,
                                 std::uint64_t epoch = 3) {
    std::vector<std::uint8_t> out(sdbu::HEADER_BYTES + 8, 0);
    std::memcpy(out.data(), "SDBU", 4);
    out[4] = 2;
    out[5] = 1;
    putBe16(out, 6, sdbu::FLAG_TIME_VALID | sdbu::FLAG_DISCONTINUITY);
    putBe16(out, 8, 72);
    out[10] = 2;
    putBe32(out, 12, 42);
    putBe64(out, 16, epoch);
    putBe64(out, 24, sequence);
    putBe64(out, 32, firstIndex);
    putBe64(out, 40, 6);
    putBe32(out, 48, 7);
    putBe32(out, 52, 192000);
    putBe64(out, 56, 144300000);
    putBe32(out, 64, 2);
    const std::array<std::int16_t, 4> iq{{0, 1, -2, 32767}};
    std::memcpy(out.data() + sdbu::HEADER_BYTES, iq.data(), sizeof(iq));
    return out;
}

bool check(bool condition, const char* message) {
    if (!condition) {
        std::cerr << "FAIL: " << message << '\n';
        return false;
    }
    return true;
}

} // namespace

int main() {
    bool ok = true;
    std::string error;
    sdbu::DatagramView decoded;
    auto valid = packet();
    ok &= check(sdbu::parseDatagram(valid.data(), valid.size(), decoded, error), "valid vector parses");
    ok &= check(decoded.wireStreamId == 42, "stream id");
    ok &= check(decoded.epoch == 3, "epoch");
    ok &= check(decoded.firstSampleIndex == 5, "first sample index");
    ok &= check(decoded.sampleRateSps == 192000, "sample rate");
    ok &= check(decoded.centerFrequencyHz == 144300000, "center frequency");
    ok &= check(decoded.sampleCount == 2 && decoded.payloadBytes == 8, "payload geometry");

    auto invalid = valid;
    invalid[11] = 1;
    ok &= check(!sdbu::parseDatagram(invalid.data(), invalid.size(), decoded, error), "reserved field rejected");
    invalid = valid;
    invalid[4] = 1;
    ok &= check(!sdbu::parseDatagram(invalid.data(), invalid.size(), decoded, error), "wire v1 rejected");
    ok &= check(!sdbu::parseDatagram(valid.data(), valid.size() - 1, decoded, error), "truncated payload rejected");
    invalid = valid;
    invalid[10] = 0;
    ok &= check(!sdbu::parseDatagram(invalid.data(), invalid.size(), decoded, error), "incoherent time flags rejected");

    sdbu::ContinuityTracker tracker;
    sdbu::parseDatagram(valid.data(), valid.size(), decoded, error);
    ok &= check(tracker.observe(decoded) == sdbu::ContinuityResult::First, "first packet accepted");
    auto continuous = packet(1, 7);
    putBe16(continuous, 6, sdbu::FLAG_TIME_VALID);
    sdbu::parseDatagram(continuous.data(), continuous.size(), decoded, error);
    ok &= check(tracker.observe(decoded) == sdbu::ContinuityResult::Continuous, "continuous packet detected");
    ok &= check(tracker.observe(decoded) == sdbu::ContinuityResult::OldOrDuplicate, "duplicate rejected");
    auto gap = packet(3, 11);
    putBe16(gap, 6, sdbu::FLAG_TIME_VALID);
    sdbu::parseDatagram(gap.data(), gap.size(), decoded, error);
    ok &= check(tracker.observe(decoded) == sdbu::ContinuityResult::Gap, "gap detected");
    auto nextEpoch = packet(0, 0, 4);
    sdbu::parseDatagram(nextEpoch.data(), nextEpoch.size(), decoded, error);
    ok &= check(tracker.observe(decoded) == sdbu::ContinuityResult::NewEpoch, "epoch transition detected");
    auto retiredEpoch = packet(4, 13, 3);
    putBe16(retiredEpoch, 6, sdbu::FLAG_TIME_VALID);
    sdbu::parseDatagram(retiredEpoch.data(), retiredEpoch.size(), decoded, error);
    ok &= check(tracker.observe(decoded) == sdbu::ContinuityResult::OldOrDuplicate,
                "late packet from retired epoch rejected");

    auto cf32 = valid;
    cf32[5] = 2;
    cf32.resize(sdbu::HEADER_BYTES + 16);
    const std::array<float, 4> floatIq{{0.25F, -0.5F, 1.0F, -1.0F}};
    std::memcpy(cf32.data() + sdbu::HEADER_BYTES, floatIq.data(), sizeof(floatIq));
    ok &= check(sdbu::parseDatagram(cf32.data(), cf32.size(), decoded, error), "CF32 vector parses");
    ok &= check(decoded.format == sdbu::SampleFormat::CF32 && decoded.payloadBytes == 16,
                "CF32 payload geometry");

    auto wrapping = valid;
    putBe64(wrapping, 24, UINT64_MAX);
    ok &= check(!sdbu::parseDatagram(wrapping.data(), wrapping.size(), decoded, error),
                "wrapping packet sequence rejected");

    if (ok) {
        std::cout << "SDBU v2 protocol tests passed\n";
        return 0;
    }
    return 1;
}

