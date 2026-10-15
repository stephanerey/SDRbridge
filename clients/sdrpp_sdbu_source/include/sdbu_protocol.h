#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

namespace sdbu {

constexpr std::size_t HEADER_BYTES = 72;
constexpr std::uint8_t VERSION = 2;
constexpr std::uint16_t FLAG_TIME_VALID = 1u << 0;
constexpr std::uint16_t FLAG_HARDWARE_ORIGIN = 1u << 1;
constexpr std::uint16_t FLAG_DISCONTINUITY = 1u << 2;
constexpr std::uint16_t FLAG_REPLAY = 1u << 3;
constexpr std::uint16_t KNOWN_FLAGS = FLAG_TIME_VALID | FLAG_HARDWARE_ORIGIN |
                                      FLAG_DISCONTINUITY | FLAG_REPLAY;

enum class SampleFormat : std::uint8_t {
    CS16 = 1,
    CF32 = 2,
};

struct DatagramView {
    SampleFormat format = SampleFormat::CS16;
    std::uint16_t flags = 0;
    std::uint8_t timeDomain = 0;
    std::uint32_t wireStreamId = 0;
    std::uint64_t epoch = 0;
    std::uint64_t packetSequence = 0;
    std::uint64_t firstSampleIndex = 0;
    std::uint64_t timestampNs = 0;
    std::uint32_t configRevision = 0;
    std::uint32_t sampleRateSps = 0;
    std::uint64_t centerFrequencyHz = 0;
    std::uint32_t sampleCount = 0;
    const std::uint8_t* payload = nullptr;
    std::size_t payloadBytes = 0;
};

bool parseDatagram(const std::uint8_t* data, std::size_t size,
                   DatagramView& out, std::string& error);

enum class ContinuityResult {
    First,
    Continuous,
    Gap,
    NewEpoch,
    OldOrDuplicate,
};

class ContinuityTracker {
public:
    ContinuityResult observe(const DatagramView& packet);
    void reset();

private:
    bool initialized_ = false;
    std::uint32_t streamId_ = 0;
    std::uint64_t epoch_ = 0;
    std::uint64_t nextSequence_ = 0;
    std::uint64_t nextSampleIndex_ = 0;
};

} // namespace sdbu
