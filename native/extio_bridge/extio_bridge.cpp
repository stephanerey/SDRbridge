#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winsock2.h>
#include <ws2tcpip.h>
#include <algorithm>
#include <atomic>
#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <limits>
#include <string>
#include <thread>
#include <vector>

#pragma comment(lib, "Ws2_32.lib")

namespace {
using ExtIOCallback = int(__cdecl*)(int count, int status, float iq_offset, void* iq_data);
#pragma pack(push, 1)
struct GlobalHeader {
    char magic[4]; uint32_t version, header_bytes, slots, slot_stride, max_samples, format;
    uint32_t publication_guard; uint64_t latest_sequence, epoch; uint8_t reserved[80];
};
struct SlotHeader {
    uint32_t guard, sample_count; uint64_t sequence, first_sample_index, timestamp_ns, epoch;
    uint32_t config_revision, sample_rate_sps; uint64_t center_frequency_hz;
    uint32_t flags, time_domain;
};
#pragma pack(pop)
static_assert(sizeof(GlobalHeader) == 128, "SDBR v2 global header size");
static_assert(sizeof(SlotHeader) == 64, "SDBR v2 slot header size");

constexpr int kExtHwUsbData16 = 3;
constexpr int kExtHwChangedSampleRate = 100;
constexpr int kExtHwChangedLo = 101;
constexpr int kCallbackSamples = 2048;
constexpr uint64_t kEmpty = UINT64_MAX;
std::atomic<ExtIOCallback> g_callback{nullptr};
SOCKET g_socket = INVALID_SOCKET;
HANDLE g_mapping = nullptr;
uint8_t* g_view = nullptr;
GlobalHeader g_header{};
std::atomic<bool> g_running{false};
std::thread g_thread;
uint64_t g_next_sequence = 0;
std::atomic<long> g_frequency{144300000};
std::atomic<long> g_sample_rate{2000000};
long g_notified_frequency = std::numeric_limits<long>::min();
long g_notified_sample_rate = std::numeric_limits<long>::min();
std::vector<int16_t> g_pending;

uint16_t control_port() {
    char value[16]{};
    const DWORD length = GetEnvironmentVariableA("SDRBRIDGE_CONTROL_PORT", value, sizeof(value));
    if (length == 0 || length >= sizeof(value)) return 47631;
    char* end = nullptr;
    const unsigned long port = std::strtoul(value, &end, 10);
    return end && *end == '\0' && port > 0 && port <= 65535
        ? static_cast<uint16_t>(port)
        : 47631;
}

void notify_host(long frequency, long sample_rate) {
    const auto callback = g_callback.load(std::memory_order_acquire);
    if (!callback) return;
    if (sample_rate != g_notified_sample_rate) {
        g_notified_sample_rate = sample_rate;
        callback(-1, kExtHwChangedSampleRate, 0.0f, nullptr);
    }
    if (frequency != g_notified_frequency) {
        g_notified_frequency = frequency;
        callback(-1, kExtHwChangedLo, 0.0f, nullptr);
    }
}

uint32_t atomic_load_u32(const uint32_t* address) {
    return static_cast<uint32_t>(InterlockedCompareExchange(
        reinterpret_cast<volatile LONG*>(const_cast<uint32_t*>(address)), 0, 0));
}

bool read_latest(uint64_t& latest) {
    for (int attempt = 0; attempt < 3; ++attempt) {
        auto before = atomic_load_u32(&reinterpret_cast<GlobalHeader*>(g_view)->publication_guard);
        if (before & 1U) continue;
        MemoryBarrier();
        std::memcpy(&latest, g_view + offsetof(GlobalHeader, latest_sequence), sizeof(latest));
        MemoryBarrier();
        auto after = atomic_load_u32(&reinterpret_cast<GlobalHeader*>(g_view)->publication_guard);
        if (before == after && !(after & 1U)) return true;
    }
    return false;
}

std::string json_string(const std::string& json, const char* key) {
    std::string marker = std::string("\"") + key + "\":\"";
    auto start = json.find(marker); if (start == std::string::npos) return {};
    start += marker.size(); auto end = json.find('"', start);
    return end == std::string::npos ? std::string{} : json.substr(start, end - start);
}
long long json_integer(const std::string& json, const char* key, long long fallback = 0) {
    std::string marker = std::string("\"") + key + "\":";
    auto start = json.find(marker); if (start == std::string::npos) return fallback;
    start += marker.size(); return _strtoi64(json.c_str() + start, nullptr, 10);
}

bool send_line(const std::string& line, std::string& response) {
    std::string wire = line + "\n";
    if (send(g_socket, wire.data(), static_cast<int>(wire.size()), 0) == SOCKET_ERROR) return false;
    response.clear(); char buffer[1024];
    while (response.find('\n') == std::string::npos) {
        int received = recv(g_socket, buffer, sizeof(buffer), 0);
        if (received <= 0) return false;
        response.append(buffer, received);
        if (response.size() > 65536) return false;
    }
    return response.find("\"ok\":true") != std::string::npos;
}

void disconnect_bridge() {
    g_running.store(false);
    if (g_thread.joinable()) g_thread.join();
    if (g_view) { UnmapViewOfFile(g_view); g_view = nullptr; }
    if (g_mapping) { CloseHandle(g_mapping); g_mapping = nullptr; }
    if (g_socket != INVALID_SOCKET) { closesocket(g_socket); g_socket = INVALID_SOCKET; }
    WSACleanup();
}

bool connect_bridge() {
    WSADATA data{}; if (WSAStartup(MAKEWORD(2, 2), &data) != 0) return false;
    g_socket = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP); if (g_socket == INVALID_SOCKET) return false;
    sockaddr_in address{}; address.sin_family = AF_INET; address.sin_port = htons(control_port()); inet_pton(AF_INET, "127.0.0.1", &address.sin_addr);
    if (connect(g_socket, reinterpret_cast<sockaddr*>(&address), sizeof(address)) == SOCKET_ERROR) { disconnect_bridge(); return false; }
    std::string response;
    if (!send_line("{\"action\":\"register\",\"name\":\"HDSDR ExtIO\"}", response)) { disconnect_bridge(); return false; }
    auto name = json_string(response, "name");
    auto slots = static_cast<uint32_t>(json_integer(response, "slot_count"));
    auto payload_bytes = static_cast<uint32_t>(json_integer(response, "payload_bytes"));
    auto block_samples = static_cast<uint32_t>(json_integer(response, "block_samples"));
    g_frequency.store(static_cast<long>(json_integer(response, "center_frequency_hz", 144300000)), std::memory_order_release);
    g_sample_rate.store(static_cast<long>(json_integer(response, "sample_rate_sps", 2000000)), std::memory_order_release);
    auto version = static_cast<uint32_t>(json_integer(response, "version"));
    if (name.empty() || version != 2 || slots < 4 || payload_bytes != block_samples * 4) { disconnect_bridge(); return false; }
    std::wstring wide(name.begin(), name.end());
    // InterlockedCompareExchange performs an atomic read-modify-write even
    // when the exchanged value is identical; the mapped page must therefore
    // be writable. This client never changes ring contents.
    g_mapping = OpenFileMappingW(FILE_MAP_READ | FILE_MAP_WRITE, FALSE, wide.c_str());
    if (!g_mapping) { disconnect_bridge(); return false; }
    g_view = static_cast<uint8_t*>(MapViewOfFile(g_mapping, FILE_MAP_READ | FILE_MAP_WRITE, 0, 0, 0));
    if (!g_view) { disconnect_bridge(); return false; }
    std::memcpy(&g_header, g_view, sizeof(g_header));
    if (std::memcmp(g_header.magic, "SDBR", 4) != 0 || g_header.version != 2 ||
        g_header.header_bytes != 128 || g_header.format != 1 || g_header.slots != slots ||
        g_header.max_samples != block_samples || g_header.slot_stride < sizeof(SlotHeader) + payload_bytes ||
        (g_header.slot_stride % 64) != 0) { disconnect_bridge(); return false; }
    uint64_t latest = kEmpty; if (!read_latest(latest)) latest = kEmpty;
    g_next_sequence = latest == kEmpty ? 0 : latest + 1;
    g_notified_frequency = std::numeric_limits<long>::min();
    g_notified_sample_rate = std::numeric_limits<long>::min();
    g_pending.clear(); g_pending.reserve(kCallbackSamples * 4);
    return true;
}

void reader_loop() {
    std::vector<int16_t> output(kCallbackSamples * 2);
    std::vector<int16_t> owned(g_header.max_samples * 2);
    while (g_running.load()) {
        uint64_t latest; if (!read_latest(latest)) { Sleep(0); continue; }
        if (latest == kEmpty || latest < g_next_sequence) { Sleep(1); continue; }
        uint64_t oldest = latest >= g_header.slots ? latest - g_header.slots + 1 : 0;
        if (g_next_sequence < oldest) g_next_sequence = oldest;
        const size_t offset = sizeof(GlobalHeader) + (g_next_sequence % g_header.slots) * g_header.slot_stride;
        bool coherent = false; SlotHeader slot{};
        for (int attempt = 0; attempt < 3; ++attempt) {
            auto before = atomic_load_u32(reinterpret_cast<uint32_t*>(g_view + offset));
            if (before & 1U) continue;
            MemoryBarrier();
            std::memcpy(&slot, g_view + offset, sizeof(slot));
            if (slot.sequence != g_next_sequence || slot.sample_count == 0 || slot.sample_count > g_header.max_samples) break;
            std::memcpy(owned.data(), g_view + offset + sizeof(SlotHeader), slot.sample_count * 4);
            MemoryBarrier();
            auto after = atomic_load_u32(reinterpret_cast<uint32_t*>(g_view + offset));
            if (before == after && !(after & 1U) && slot.sequence == g_next_sequence) { coherent = true; break; }
        }
        if (!coherent) { ++g_next_sequence; continue; }
        const long frequency = static_cast<long>(slot.center_frequency_hz);
        const long sample_rate = static_cast<long>(slot.sample_rate_sps);
        g_frequency.store(frequency, std::memory_order_release);
        g_sample_rate.store(sample_rate, std::memory_order_release);
        notify_host(frequency, sample_rate);
        g_pending.insert(g_pending.end(), owned.begin(), owned.begin() + slot.sample_count * 2);
        ++g_next_sequence;
        while (g_pending.size() >= output.size()) {
            std::copy_n(g_pending.begin(), output.size(), output.begin());
            g_pending.erase(g_pending.begin(), g_pending.begin() + output.size());
            const auto callback = g_callback.load(std::memory_order_acquire);
            if (callback) callback(kCallbackSamples, 0, 0.0f, output.data());
        }
    }
}
}

extern "C" bool __stdcall InitHW(char* name, char* model, int& type) {
    std::strncpy(name, "SDR_Bridge", 15); name[15] = 0;
    std::strncpy(model, "Local IQ", 15); model[15] = 0;
    type = kExtHwUsbData16; return true;
}
extern "C" bool __stdcall OpenHW() { return connect_bridge(); }
extern "C" void __stdcall CloseHW() { disconnect_bridge(); }
extern "C" int __stdcall StartHW(long) {
    if (!g_view || !g_callback.load(std::memory_order_acquire)) return 0;
    if (!g_running.exchange(true)) g_thread = std::thread(reader_loop);
    return kCallbackSamples;
}
extern "C" void __stdcall StopHW() {
    g_running.store(false); if (g_thread.joinable()) g_thread.join();
}
extern "C" void __stdcall SetCallback(ExtIOCallback callback) { g_callback.store(callback, std::memory_order_release); }
extern "C" int __stdcall SetHWLO(long requested_frequency) {
    const long frequency = g_frequency.load(std::memory_order_acquire);
    if (requested_frequency < frequency) return -frequency;
    if (requested_frequency > frequency) return frequency;
    return 0;
}
extern "C" long __stdcall GetHWLO() { return g_frequency.load(std::memory_order_acquire); }
extern "C" long __stdcall GetHWSR() { return g_sample_rate.load(std::memory_order_acquire); }
extern "C" int __stdcall GetStatus() { return g_view ? 0 : 1; }
extern "C" void __stdcall ShowGUI() { MessageBoxA(nullptr, "All SDR settings are controlled by SDR_Bridge.exe", "ExtIO_SDR_Bridge", MB_OK | MB_ICONINFORMATION); }
extern "C" void __stdcall HideGUI() {}
