#define SDRPLAY_BRIDGE_EXPORTS
#include "sdrplay_bridge.h"
#include <sdrplay_api.h>
#include <algorithm>
#include <atomic>
#include <cstring>
#include <condition_variable>
#include <chrono>
#include <deque>
#include <mutex>
#include <string>
#include <vector>

namespace {
std::mutex g_mutex;
sdrplay_api_DeviceT g_device{};
sdrplay_api_DeviceParamsT* g_params = nullptr;
sdrplay_api_RxChannelParamsT* g_rx = nullptr;
sdb_iq_callback g_callback = nullptr;
void* g_context = nullptr;
std::string g_error;
std::string g_serial;
std::atomic<bool> g_open{false};
float g_api_version = 0.0f;

struct QueuedBlock {
    std::vector<int16_t> samples;
    uint64_t first_sample = 0;
};
std::mutex g_queue_mutex;
std::condition_variable g_queue_cv;
std::deque<QueuedBlock> g_queue;
constexpr size_t kMaxQueuedBlocks = 32;

int fail(sdrplay_api_ErrT error, const char* operation) {
    g_error = std::string(operation) + ": " + sdrplay_api_GetErrorString(error);
    const int code = static_cast<int>(error);
    return code == 0 ? -1 : -code;
}

sdrplay_api_Bw_MHzT bandwidth_from_khz(int value) {
    const struct { int khz; sdrplay_api_Bw_MHzT type; } values[] = {
        {200, sdrplay_api_BW_0_200}, {300, sdrplay_api_BW_0_300},
        {600, sdrplay_api_BW_0_600}, {1536, sdrplay_api_BW_1_536},
        {5000, sdrplay_api_BW_5_000}, {6000, sdrplay_api_BW_6_000},
        {7000, sdrplay_api_BW_7_000}, {8000, sdrplay_api_BW_8_000},
    };
    auto best = values[0];
    for (const auto& candidate : values) {
        if (std::abs(candidate.khz - value) < std::abs(best.khz - value)) best = candidate;
    }
    return best.type;
}

void stream_a(short* xi, short* xq, sdrplay_api_StreamCbParamsT* params,
              unsigned int num_samples, unsigned int reset, void*) {
    if (!g_open.load(std::memory_order_acquire) || reset || !xi || !xq) return;
    // Le callback SDRplay ne traverse jamais Python/ctypes. Une mise à jour
    // RF peut donc se terminer sans attendre le GIL ni le traitement DSP.
    QueuedBlock block;
    block.samples.resize(static_cast<size_t>(num_samples) * 2);
    for (unsigned int i = 0; i < num_samples; ++i) {
        block.samples[2 * i] = xi[i];
        block.samples[2 * i + 1] = xq[i];
    }
    block.first_sample = params ? params->firstSampleNum : 0;
    {
        std::lock_guard<std::mutex> lock(g_queue_mutex);
        if (g_queue.size() >= kMaxQueuedBlocks) {
            // Le flux matériel ne doit jamais être bloqué par le consommateur;
            // on sacrifie le plus ancien bloc et le compteur de pertes reste
            // visible côté bridge via la discontinuité de séquence.
            g_queue.pop_front();
        }
        g_queue.emplace_back(std::move(block));
    }
    g_queue_cv.notify_one();
}

void stream_b(short*, short*, sdrplay_api_StreamCbParamsT*, unsigned int, unsigned int, void*) {}

void event_callback(sdrplay_api_EventT event_id, sdrplay_api_TunerSelectT tuner,
                    sdrplay_api_EventParamsT*, void*) {
    if (event_id == sdrplay_api_PowerOverloadChange && g_device.dev) {
        sdrplay_api_Update(g_device.dev, tuner, sdrplay_api_Update_Ctrl_OverloadMsgAck,
                           sdrplay_api_Update_Ext1_None);
    } else if (event_id == sdrplay_api_DeviceRemoved) {
        g_error = "SDRplay device removed";
        g_open.store(false, std::memory_order_release);
    }
}

void cleanup_unlocked() {
    g_open.store(false, std::memory_order_release);
    g_queue_cv.notify_all();
    if (g_device.dev) {
        sdrplay_api_Uninit(g_device.dev);
        sdrplay_api_ReleaseDevice(&g_device);
    }
    sdrplay_api_Close();
    std::memset(&g_device, 0, sizeof(g_device));
    g_params = nullptr; g_rx = nullptr; g_callback = nullptr; g_context = nullptr;
    {
        std::lock_guard<std::mutex> queue_lock(g_queue_mutex);
        g_queue.clear();
    }
}
}

extern "C" int __cdecl sdb_open(double sample_rate_hz, double frequency_hz, int bandwidth_khz,
                                  int gain_reduction_db, int agc_enabled,
                                  sdb_iq_callback callback, void* context) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_open.load()) return -100;
    g_error.clear(); g_serial.clear();
    {
        std::lock_guard<std::mutex> queue_lock(g_queue_mutex);
        g_queue.clear();
    }
    auto error = sdrplay_api_Open();
    if (error != sdrplay_api_Success) return fail(error, "Open");
    error = sdrplay_api_ApiVersion(&g_api_version);
    if (error != sdrplay_api_Success) { cleanup_unlocked(); return fail(error, "ApiVersion"); }
    if (g_api_version < 3.15f) { cleanup_unlocked(); g_error = "SDRplay API 3.15 or later is required"; return -101; }

    sdrplay_api_DeviceT devices[SDRPLAY_MAX_DEVICES]{};
    unsigned int count = 0;
    error = sdrplay_api_LockDeviceApi();
    if (error != sdrplay_api_Success) { cleanup_unlocked(); return fail(error, "LockDeviceApi"); }
    error = sdrplay_api_GetDevices(devices, &count, SDRPLAY_MAX_DEVICES);
    if (error == sdrplay_api_Success && count > 0) {
        g_device = devices[0];
        error = sdrplay_api_SelectDevice(&g_device);
    } else if (error == sdrplay_api_Success) {
        error = sdrplay_api_Fail;
        g_error = "No SDRplay device found";
    }
    sdrplay_api_UnlockDeviceApi();
    if (error != sdrplay_api_Success || count == 0) {
        if (g_error.empty()) fail(error, "SelectDevice");
        cleanup_unlocked(); return -static_cast<int>(error);
    }
    g_serial = g_device.SerNo;
    error = sdrplay_api_GetDeviceParams(g_device.dev, &g_params);
    if (error != sdrplay_api_Success || !g_params || !g_params->devParams || !g_params->rxChannelA) {
        cleanup_unlocked(); return fail(error, "GetDeviceParams");
    }
    g_rx = g_params->rxChannelA;
    g_params->devParams->fsFreq.fsHz = sample_rate_hz;
    g_rx->tunerParams.rfFreq.rfHz = frequency_hz;
    g_rx->tunerParams.bwType = bandwidth_from_khz(bandwidth_khz);
    g_rx->tunerParams.ifType = sdrplay_api_IF_Zero;
    g_rx->tunerParams.gain.gRdB = std::clamp(gain_reduction_db, 20, 59);
    g_rx->ctrlParams.agc.enable = agc_enabled ? sdrplay_api_AGC_50HZ : sdrplay_api_AGC_DISABLE;
    g_callback = callback; g_context = context;
    sdrplay_api_CallbackFnsT callbacks{stream_a, stream_b, event_callback};
    error = sdrplay_api_Init(g_device.dev, &callbacks, nullptr);
    if (error != sdrplay_api_Success) { cleanup_unlocked(); return fail(error, "Init"); }
    g_open.store(true, std::memory_order_release);
    return 0;
}

extern "C" int __cdecl sdb_close(void) {
    std::lock_guard<std::mutex> lock(g_mutex);
    cleanup_unlocked(); return 0;
}

extern "C" int __cdecl sdb_set_frequency(double frequency_hz) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (!g_open.load() || !g_rx) return -100;
    g_rx->tunerParams.rfFreq.rfHz = frequency_hz;
    auto error = sdrplay_api_Update(g_device.dev, g_device.tuner, sdrplay_api_Update_Tuner_Frf, sdrplay_api_Update_Ext1_None);
    return error == sdrplay_api_Success ? 0 : fail(error, "Update frequency");
}

extern "C" int __cdecl sdb_set_gain(int gain_reduction_db, int agc_enabled) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (!g_open.load() || !g_rx) return -100;
    g_rx->tunerParams.gain.gRdB = std::clamp(gain_reduction_db, 20, 59);
    g_rx->ctrlParams.agc.enable = agc_enabled ? sdrplay_api_AGC_50HZ : sdrplay_api_AGC_DISABLE;
    auto reason = static_cast<sdrplay_api_ReasonForUpdateT>(sdrplay_api_Update_Tuner_Gr | sdrplay_api_Update_Ctrl_Agc);
    auto error = sdrplay_api_Update(g_device.dev, g_device.tuner, reason, sdrplay_api_Update_Ext1_None);
    return error == sdrplay_api_Success ? 0 : fail(error, "Update gain");
}

extern "C" int __cdecl sdb_set_bandwidth(int bandwidth_khz) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (!g_open.load() || !g_rx) return -100;
    g_rx->tunerParams.bwType = bandwidth_from_khz(bandwidth_khz);
    auto error = sdrplay_api_Update(g_device.dev, g_device.tuner, sdrplay_api_Update_Tuner_BwType, sdrplay_api_Update_Ext1_None);
    return error == sdrplay_api_Success ? 0 : fail(error, "Update bandwidth");
}

extern "C" int __cdecl sdb_read_iq(int16_t* interleaved_iq, uint32_t capacity_samples,
                                    uint32_t* sample_count, uint64_t* first_sample,
                                    int timeout_ms) {
    if (!interleaved_iq || !sample_count || !first_sample || capacity_samples == 0) return -102;
    std::unique_lock<std::mutex> lock(g_queue_mutex);
    const auto ready = [=] { return !g_queue.empty() || !g_open.load(std::memory_order_acquire); };
    if (g_queue.empty() && timeout_ms > 0) {
        g_queue_cv.wait_for(lock, std::chrono::milliseconds(timeout_ms), ready);
    }
    if (g_queue.empty()) {
        *sample_count = 0;
        return g_open.load(std::memory_order_acquire) ? 0 : -100;
    }
    QueuedBlock block = std::move(g_queue.front());
    g_queue.pop_front();
    lock.unlock();
    const uint32_t available = static_cast<uint32_t>(block.samples.size() / 2);
    if (available > capacity_samples) return -103;
    std::memcpy(interleaved_iq, block.samples.data(), block.samples.size() * sizeof(int16_t));
    *sample_count = available;
    *first_sample = block.first_sample;
    return 1;
}

extern "C" int __cdecl sdb_set_options(int antenna, int bias_t, int rf_notch, int rf_dab_notch, int hdr_enable, int hdr_bw, int lna_state, int if_type) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (!g_open.load() || !g_params || !g_rx) return -100;
    if (g_device.hwVer != SDRPLAY_RSPdx_ID && g_device.hwVer != SDRPLAY_RSPdxR2_ID) return -103;
    if (antenna < 0 || antenna > 2 || hdr_bw < 0 || hdr_bw > 3 || lna_state < 0 || lna_state > 27 || if_type < 0 || if_type > 3) return -102;
    g_params->devParams->rspDxParams.antennaSel = static_cast<sdrplay_api_RspDx_AntennaSelectT>(antenna);
    g_params->devParams->rspDxParams.biasTEnable = bias_t ? 1 : 0;
    g_params->devParams->rspDxParams.rfNotchEnable = rf_notch ? 1 : 0;
    g_params->devParams->rspDxParams.rfDabNotchEnable = rf_dab_notch ? 1 : 0;
    g_params->devParams->rspDxParams.hdrEnable = hdr_enable ? 1 : 0;
    g_rx->rspDxTunerParams.hdrBw = static_cast<sdrplay_api_RspDx_HdrModeBwT>(hdr_bw);
    g_rx->tunerParams.gain.LNAstate = static_cast<unsigned char>(lna_state);
    const sdrplay_api_If_kHzT if_values[] = {sdrplay_api_IF_Zero, sdrplay_api_IF_0_450, sdrplay_api_IF_1_620, sdrplay_api_IF_2_048};
    g_rx->tunerParams.ifType = if_values[if_type];
    // Les options RSPdx sont dans le masque d'extension Ext1. Les mélanger
    // au masque principal (ReasonForUpdate) est accepté par certaines
    // versions de l'API mais n'applique pas les réglages au périphérique.
    const auto ext = static_cast<sdrplay_api_ReasonForUpdateExtension1T>(
        sdrplay_api_Update_RspDx_AntennaControl |
        sdrplay_api_Update_RspDx_BiasTControl |
        sdrplay_api_Update_RspDx_RfNotchControl |
        sdrplay_api_Update_RspDx_RfDabNotchControl |
        sdrplay_api_Update_RspDx_HdrEnable |
        sdrplay_api_Update_RspDx_HdrBw);
    auto error = sdrplay_api_Update(g_device.dev, g_device.tuner,
                                    sdrplay_api_Update_None, ext);
    if (error != sdrplay_api_Success) return fail(error, "Update RSPdx options");
    const auto tuner = static_cast<sdrplay_api_ReasonForUpdateT>(
        sdrplay_api_Update_Tuner_Gr | sdrplay_api_Update_Tuner_IfType);
    error = sdrplay_api_Update(g_device.dev, g_device.tuner, tuner,
                               sdrplay_api_Update_Ext1_None);
    return error == sdrplay_api_Success ? 0 : fail(error, "Update RSPdx gain/IF");
}

extern "C" const char* __cdecl sdb_last_error(void) { return g_error.c_str(); }
extern "C" const char* __cdecl sdb_serial(void) { return g_serial.c_str(); }
extern "C" int __cdecl sdb_hardware_version(void) { return static_cast<int>(g_device.hwVer); }
extern "C" float __cdecl sdb_api_version(void) { return g_api_version; }
