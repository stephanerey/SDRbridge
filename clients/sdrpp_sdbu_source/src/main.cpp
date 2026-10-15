#include <winsock2.h>
#include <ws2tcpip.h>

#include <module.h>
#include <core.h>
#include <config.h>
#include <gui/smgui.h>
#include <gui/tuner.h>
#include <gui/widgets/waterfall.h>
#include <signal_path/source.h>
#include <utils/flog.h>

#include "sdbu_protocol.h"

#include <algorithm>
#include <array>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <string>
#include <thread>

namespace sigpath {
    SDRPP_EXPORT SourceManager sourceManager;
}
namespace gui {
    SDRPP_EXPORT ImGui::WaterFall waterfall;
}

SDRPP_MOD_INFO{
    /* Name:            */ "sdbu_source",
    /* Description:     */ "SDRbridge SDBU v2 UDP source",
    /* Author:          */ "SDRbridge contributors",
    /* Version:         */ 0, 1, 1,
    /* Max instances:   */ 1
};

namespace {

constexpr const char* SOURCE_NAME = "SDRbridge SDBU v2";
constexpr int DEFAULT_PORT = 7355;
constexpr int DEFAULT_SAMPLE_RATE = 192000;
constexpr DWORD RECEIVE_TIMEOUT_MS = 50;
constexpr int RECEIVE_BUFFER_BYTES = 4 * 1024 * 1024;

ConfigManager config;
bool winsockReady = false;

class SdbuSourceModule : public ModuleManager::Instance {
public:
    explicit SdbuSourceModule(std::string name) : name_(std::move(name)) {
        handler_.ctx = this;
        handler_.selectHandler = menuSelected;
        handler_.deselectHandler = menuDeselected;
        handler_.menuHandler = menuHandler;
        handler_.startHandler = start;
        handler_.stopHandler = stop;
        handler_.tuneHandler = tune;
        handler_.stream = &stream_;

        loadConfig();
        sigpath::sourceManager.registerSource(SOURCE_NAME, &handler_);
    }

    ~SdbuSourceModule() override {
        stop(this);
        sigpath::sourceManager.unregisterSource(SOURCE_NAME);
    }

    void postInit() override {}
    void enable() override { enabled_ = true; }
    void disable() override { enabled_ = false; }
    bool isEnabled() override { return enabled_; }

private:
    void loadConfig() {
        config.acquire();
        auto& node = config.conf[name_];
        bool changed = false;
        if (node.contains("bind_address") && node["bind_address"].is_string()) {
            const auto value = node["bind_address"].get<std::string>();
            std::snprintf(bindAddress_, sizeof(bindAddress_), "%s", value.c_str());
        }
        else {
            node["bind_address"] = bindAddress_;
            changed = true;
        }
        if (node.contains("port") && node["port"].is_number_integer()) {
            port_ = std::clamp(node["port"].get<int>(), 1, 65535);
        }
        else {
            node["port"] = port_;
            changed = true;
        }
        if (node.contains("fallback_sample_rate") && node["fallback_sample_rate"].is_number_integer()) {
            fallbackSampleRate_ = std::max(node["fallback_sample_rate"].get<int>(), 1000);
        }
        else {
            node["fallback_sample_rate"] = fallbackSampleRate_;
            changed = true;
        }
        config.release(changed);
        currentSampleRate_.store(static_cast<std::uint32_t>(fallbackSampleRate_));
    }

    void saveEndpointConfig() {
        config.acquire();
        config.conf[name_]["bind_address"] = bindAddress_;
        config.conf[name_]["port"] = port_;
        config.conf[name_]["fallback_sample_rate"] = fallbackSampleRate_;
        config.release(true);
    }

    static void menuSelected(void* ctx) {
        auto* self = static_cast<SdbuSourceModule*>(ctx);
        self->selected_.store(true);
        core::setInputSampleRate(self->currentSampleRate_.load());
        if (!core::args["server"].b()) {
            gui::waterfall.centerFrequencyLocked = true;
        }
        self->syncDisplayedFrequency(self->centerFrequencyHz_.load());
        flog::info("SDBU source '{}': selected", self->name_.c_str());
    }

    static void menuDeselected(void* ctx) {
        auto* self = static_cast<SdbuSourceModule*>(ctx);
        self->selected_.store(false);
        if (!core::args["server"].b()) {
            gui::waterfall.centerFrequencyLocked = false;
        }
        flog::info("SDBU source '{}': deselected", self->name_.c_str());
    }

    static void start(void* ctx) {
        auto* self = static_cast<SdbuSourceModule*>(ctx);
        if (self->running_.load()) {
            return;
        }
        if (!winsockReady) {
            self->setLastError("Winsock is not initialized");
            flog::error("SDBU source: Winsock is not initialized");
            return;
        }

        const SOCKET socketHandle = ::socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
        if (socketHandle == INVALID_SOCKET) {
            self->setSocketError("socket", WSAGetLastError());
            return;
        }

        DWORD timeout = RECEIVE_TIMEOUT_MS;
        ::setsockopt(socketHandle, SOL_SOCKET, SO_RCVTIMEO,
                     reinterpret_cast<const char*>(&timeout), sizeof(timeout));
        int receiveBytes = RECEIVE_BUFFER_BYTES;
        ::setsockopt(socketHandle, SOL_SOCKET, SO_RCVBUF,
                     reinterpret_cast<const char*>(&receiveBytes), sizeof(receiveBytes));

        sockaddr_in local{};
        local.sin_family = AF_INET;
        local.sin_port = htons(static_cast<u_short>(self->port_));
        if (::inet_pton(AF_INET, self->bindAddress_, &local.sin_addr) != 1) {
            ::closesocket(socketHandle);
            self->setLastError("Bind address must be an IPv4 literal");
            flog::error("SDBU source: invalid bind address '{}'", self->bindAddress_);
            return;
        }
        if (::bind(socketHandle, reinterpret_cast<sockaddr*>(&local), sizeof(local)) == SOCKET_ERROR) {
            const int error = WSAGetLastError();
            ::closesocket(socketHandle);
            self->setSocketError("bind", error);
            return;
        }

        {
            std::lock_guard<std::mutex> lock(self->socketMutex_);
            self->socket_ = socketHandle;
        }
        self->tracker_.reset();
        self->metadataLogged_ = false;
        self->running_.store(true);
        self->receiverAlive_.store(true);
        self->workerThread_ = std::thread(&SdbuSourceModule::worker, self);
        flog::info("SDBU source '{}': listening on {}:{}", self->name_.c_str(),
                   self->bindAddress_, self->port_);
    }

    static void stop(void* ctx) {
        auto* self = static_cast<SdbuSourceModule*>(ctx);
        if (!self->running_.exchange(false)) {
            if (self->workerThread_.joinable()) {
                self->workerThread_.join();
            }
            return;
        }
        self->closeSocket();
        self->stream_.stopWriter();
        if (self->workerThread_.joinable()) {
            self->workerThread_.join();
        }
        self->stream_.clearWriteStop();
        self->receiverAlive_.store(false);
        flog::info("SDBU source '{}': stopped", self->name_.c_str());
    }

    static void tune(double frequency, void* ctx) {
        auto* self = static_cast<SdbuSourceModule*>(ctx);
        self->requestedUiFrequency_.store(frequency);
        // SDBU is a read-only IQ transport. Restore the authoritative frequency
        // advertised by SDRbridge instead of sending an RF command upstream.
        const auto effectiveFrequency = self->centerFrequencyHz_.load();
        if (effectiveFrequency != 0 &&
            std::llround(frequency) != static_cast<long long>(effectiveFrequency)) {
            self->syncDisplayedFrequency(effectiveFrequency);
        }
    }

    static void menuHandler(void* ctx) {
        auto* self = static_cast<SdbuSourceModule*>(ctx);
        const bool running = self->running_.load();

        if (running) {
            SmGui::BeginDisabled();
        }
        SmGui::LeftLabel("Bind IPv4");
        SmGui::FillWidth();
        bool changed = SmGui::InputText(("##sdbu_bind_" + self->name_).c_str(),
                                        self->bindAddress_, sizeof(self->bindAddress_));
        SmGui::LeftLabel("UDP port");
        SmGui::FillWidth();
        if (SmGui::InputInt(("##sdbu_port_" + self->name_).c_str(), &self->port_, 0, 0)) {
            self->port_ = std::clamp(self->port_, 1, 65535);
            changed = true;
        }
        SmGui::LeftLabel("Fallback rate");
        SmGui::FillWidth();
        if (SmGui::InputInt(("##sdbu_rate_" + self->name_).c_str(),
                            &self->fallbackSampleRate_, 0, 0)) {
            self->fallbackSampleRate_ = std::max(self->fallbackSampleRate_, 1000);
            self->currentSampleRate_.store(static_cast<std::uint32_t>(self->fallbackSampleRate_));
            changed = true;
        }
        if (changed) {
            self->saveEndpointConfig();
            if (self->selected_.load()) {
                core::setInputSampleRate(self->currentSampleRate_.load());
            }
        }
        if (running) {
            SmGui::EndDisabled();
        }

        if (running && self->receiverAlive_.load()) {
            SmGui::TextColored(ImVec4(0.2F, 1.0F, 0.2F, 1.0F), "Receiving SDBU v2 UDP");
        }
        else if (running) {
            SmGui::TextColored(ImVec4(1.0F, 0.3F, 0.2F, 1.0F), "Receiver stopped after a socket error");
        }
        else {
            SmGui::Text("Stopped");
        }

        char line[256];
        const auto streamId = self->wireStreamId_.load();
        const auto epoch = self->epoch_.load();
        const auto rate = self->currentSampleRate_.load();
        const auto frequency = self->centerFrequencyHz_.load();
        const auto revision = self->configRevision_.load();
        const auto format = self->sampleFormat_.load();
        std::snprintf(line, sizeof(line), "Stream %u | epoch %llu | rev %u",
                      streamId, static_cast<unsigned long long>(epoch), revision);
        SmGui::Text(line);
        std::snprintf(line, sizeof(line), "%s | %u S/s | %llu Hz",
                      format == 2 ? "CF32" : "CS16", rate,
                      static_cast<unsigned long long>(frequency));
        SmGui::Text(line);
        std::snprintf(line, sizeof(line), "Packets %llu | invalid %llu | gaps %llu | old %llu",
                      static_cast<unsigned long long>(self->validPackets_.load()),
                      static_cast<unsigned long long>(self->invalidPackets_.load()),
                      static_cast<unsigned long long>(self->gapEvents_.load()),
                      static_cast<unsigned long long>(self->oldPackets_.load()));
        SmGui::Text(line);
        std::snprintf(line, sizeof(line), "Socket errors %llu | sanitized CF32 %llu",
                      static_cast<unsigned long long>(self->socketErrors_.load()),
                      static_cast<unsigned long long>(self->sanitizedSamples_.load()));
        SmGui::Text(line);

        std::string sender;
        std::string error;
        {
            std::lock_guard<std::mutex> lock(self->statusMutex_);
            sender = self->lastSender_;
            error = self->lastError_;
        }
        if (!sender.empty()) {
            SmGui::Text(("Sender: " + sender).c_str());
        }
        if (!error.empty()) {
            SmGui::TextColored(ImVec4(1.0F, 0.5F, 0.2F, 1.0F), error.c_str());
        }
        if (SmGui::Button(("Reset counters##sdbu_reset_" + self->name_).c_str())) {
            self->validPackets_.store(0);
            self->invalidPackets_.store(0);
            self->gapEvents_.store(0);
            self->oldPackets_.store(0);
            self->socketErrors_.store(0);
            self->sanitizedSamples_.store(0);
        }
    }

    void worker() {
        std::array<std::uint8_t, 65535> buffer{};
        std::size_t pendingSamples = 0;
        std::uint32_t pendingRate = 0;
        std::uint32_t pendingStream = 0;
        std::uint64_t pendingEpoch = 0;
        std::uint8_t pendingFormat = 0;

        auto flush = [&]() -> bool {
            if (pendingSamples == 0) {
                return true;
            }
            const int count = static_cast<int>(pendingSamples);
            pendingSamples = 0;
            return stream_.swap(count);
        };

        while (running_.load()) {
            sockaddr_in sender{};
            int senderLength = sizeof(sender);
            SOCKET activeSocket = INVALID_SOCKET;
            {
                std::lock_guard<std::mutex> lock(socketMutex_);
                activeSocket = socket_;
            }
            if (activeSocket == INVALID_SOCKET) {
                break;
            }
            const int received = ::recvfrom(activeSocket,
                                            reinterpret_cast<char*>(buffer.data()),
                                            static_cast<int>(buffer.size()), 0,
                                            reinterpret_cast<sockaddr*>(&sender),
                                            &senderLength);
            if (received == SOCKET_ERROR) {
                const int error = WSAGetLastError();
                if (!running_.load()) {
                    break;
                }
                if (error == WSAETIMEDOUT || error == WSAEWOULDBLOCK) {
                    if (!flush()) {
                        break;
                    }
                    continue;
                }
                setSocketError("recvfrom", error);
                break;
            }

            char senderAddress[INET_ADDRSTRLEN]{};
            ::inet_ntop(AF_INET, &sender.sin_addr, senderAddress, sizeof(senderAddress));
            {
                std::lock_guard<std::mutex> lock(statusMutex_);
                lastSender_ = std::string(senderAddress) + ":" + std::to_string(ntohs(sender.sin_port));
            }

            sdbu::DatagramView packet;
            std::string parseError;
            if (!sdbu::parseDatagram(buffer.data(), static_cast<std::size_t>(received),
                                     packet, parseError)) {
                invalidPackets_.fetch_add(1);
                setLastError(parseError);
                continue;
            }

            const auto continuity = tracker_.observe(packet);
            if (continuity == sdbu::ContinuityResult::OldOrDuplicate) {
                oldPackets_.fetch_add(1);
                continue;
            }
            const bool boundary = continuity == sdbu::ContinuityResult::NewEpoch ||
                                  continuity == sdbu::ContinuityResult::Gap ||
                                  (packet.flags & sdbu::FLAG_DISCONTINUITY) != 0 ||
                                  (pendingSamples != 0 &&
                                   (pendingRate != packet.sampleRateSps ||
                                    pendingStream != packet.wireStreamId ||
                                    pendingEpoch != packet.epoch ||
                                    pendingFormat != static_cast<std::uint8_t>(packet.format)));
            if (boundary) {
                if (!flush()) {
                    break;
                }
                if (continuity == sdbu::ContinuityResult::Gap) {
                    gapEvents_.fetch_add(1);
                }
            }

            pendingRate = packet.sampleRateSps;
            pendingStream = packet.wireStreamId;
            pendingEpoch = packet.epoch;
            pendingFormat = static_cast<std::uint8_t>(packet.format);
            wireStreamId_.store(packet.wireStreamId);
            epoch_.store(packet.epoch);
            configRevision_.store(packet.configRevision);
            const auto previousFrequency = centerFrequencyHz_.exchange(packet.centerFrequencyHz);
            sampleFormat_.store(pendingFormat);
            validPackets_.fetch_add(1);

            if (!metadataLogged_ || continuity == sdbu::ContinuityResult::NewEpoch) {
                metadataLogged_ = true;
                flog::info(
                    "SDBU source '{}': receiving stream {}, epoch {}, {} S/s, {} Hz, format {}",
                    name_.c_str(), packet.wireStreamId, packet.epoch, packet.sampleRateSps,
                    packet.centerFrequencyHz,
                    packet.format == sdbu::SampleFormat::CF32 ? "CF32" : "CS16");
            }

            const auto previousRate = currentSampleRate_.exchange(packet.sampleRateSps);
            if (previousRate != packet.sampleRateSps && selected_.load()) {
                core::setInputSampleRate(packet.sampleRateSps);
            }
            if (previousFrequency != packet.centerFrequencyHz && selected_.load()) {
                syncDisplayedFrequency(packet.centerFrequencyHz);
            }

            const std::size_t targetSamples = std::clamp<std::size_t>(
                static_cast<std::size_t>(packet.sampleRateSps / 200), 256u,
                static_cast<std::size_t>(STREAM_BUFFER_SIZE));

            for (std::size_t i = 0; i < packet.sampleCount; ++i) {
                if (pendingSamples >= STREAM_BUFFER_SIZE) {
                    if (!flush()) {
                        running_.store(false);
                        break;
                    }
                }
                auto& sample = stream_.writeBuf[pendingSamples++];
                if (packet.format == sdbu::SampleFormat::CS16) {
                    std::int16_t iv = 0;
                    std::int16_t qv = 0;
                    std::memcpy(&iv, packet.payload + i * 4, sizeof(iv));
                    std::memcpy(&qv, packet.payload + i * 4 + 2, sizeof(qv));
                    sample.re = static_cast<float>(iv) / 32768.0F;
                    sample.im = static_cast<float>(qv) / 32768.0F;
                }
                else {
                    float iv = 0.0F;
                    float qv = 0.0F;
                    std::memcpy(&iv, packet.payload + i * 8, sizeof(iv));
                    std::memcpy(&qv, packet.payload + i * 8 + 4, sizeof(qv));
                    if (!std::isfinite(iv) || !std::isfinite(qv)) {
                        iv = 0.0F;
                        qv = 0.0F;
                        sanitizedSamples_.fetch_add(1);
                    }
                    sample.re = iv;
                    sample.im = qv;
                }
                if (pendingSamples >= targetSamples) {
                    if (!flush()) {
                        running_.store(false);
                        break;
                    }
                }
            }
        }

        if (pendingSamples != 0 && running_.load()) {
            flush();
        }
        closeSocket();
        receiverAlive_.store(false);
    }

    void closeSocket() {
        SOCKET handle = INVALID_SOCKET;
        {
            std::lock_guard<std::mutex> lock(socketMutex_);
            handle = socket_;
            socket_ = INVALID_SOCKET;
        }
        if (handle != INVALID_SOCKET) {
            ::shutdown(handle, SD_BOTH);
            ::closesocket(handle);
        }
    }

    void syncDisplayedFrequency(std::uint64_t frequency) {
        if (frequency == 0 || core::args["server"].b()) {
            return;
        }
        // This is the same path SDR++ uses for an externally reported center
        // frequency. Center mode also resets the selected VFO offset, keeping
        // the top frequency selector, VFO and waterfall scale consistent.
        tuner::tune(tuner::TUNER_MODE_CENTER, gui::waterfall.selectedVFO,
                    static_cast<double>(frequency));
    }

    void setLastError(const std::string& error) {
        std::lock_guard<std::mutex> lock(statusMutex_);
        lastError_ = error;
    }

    void setSocketError(const char* operation, int error) {
        socketErrors_.fetch_add(1);
        const std::string message = std::string(operation) + " failed (Winsock " +
                                    std::to_string(error) + ")";
        setLastError(message);
        flog::error("SDBU source: {}", message.c_str());
    }

    std::string name_;
    bool enabled_ = true;
    SourceManager::SourceHandler handler_{};
    dsp::stream<dsp::complex_t> stream_;

    char bindAddress_[64] = "127.0.0.1";
    int port_ = DEFAULT_PORT;
    int fallbackSampleRate_ = DEFAULT_SAMPLE_RATE;

    std::atomic<bool> selected_{false};
    std::atomic<bool> running_{false};
    std::atomic<bool> receiverAlive_{false};
    std::thread workerThread_;
    std::mutex socketMutex_;
    SOCKET socket_ = INVALID_SOCKET;
    sdbu::ContinuityTracker tracker_;
    bool metadataLogged_ = false;

    std::atomic<std::uint32_t> currentSampleRate_{DEFAULT_SAMPLE_RATE};
    std::atomic<std::uint64_t> centerFrequencyHz_{0};
    std::atomic<std::uint32_t> wireStreamId_{0};
    std::atomic<std::uint64_t> epoch_{0};
    std::atomic<std::uint32_t> configRevision_{0};
    std::atomic<std::uint8_t> sampleFormat_{1};
    std::atomic<double> requestedUiFrequency_{0.0};

    std::atomic<std::uint64_t> validPackets_{0};
    std::atomic<std::uint64_t> invalidPackets_{0};
    std::atomic<std::uint64_t> gapEvents_{0};
    std::atomic<std::uint64_t> oldPackets_{0};
    std::atomic<std::uint64_t> socketErrors_{0};
    std::atomic<std::uint64_t> sanitizedSamples_{0};

    std::mutex statusMutex_;
    std::string lastSender_;
    std::string lastError_;
};

} // namespace

MOD_EXPORT void _INIT_() {
    WSADATA data{};
    winsockReady = WSAStartup(MAKEWORD(2, 2), &data) == 0;
    json defaults = json::object();
    config.setPath(core::args["root"].s() + "/sdbu_source_config.json");
    config.load(defaults);
    config.enableAutoSave();
}

MOD_EXPORT ModuleManager::Instance* _CREATE_INSTANCE_(std::string name) {
    return new SdbuSourceModule(std::move(name));
}

MOD_EXPORT void _DELETE_INSTANCE_(ModuleManager::Instance* instance) {
    delete static_cast<SdbuSourceModule*>(instance);
}

MOD_EXPORT void _END_() {
    config.disableAutoSave();
    config.save();
    if (winsockReady) {
        WSACleanup();
        winsockReady = false;
    }
}

