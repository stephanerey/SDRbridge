#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <atomic>
#include <cstdlib>
#include <cstdio>

std::atomic<long long> samples{0};
std::atomic<int> lo_events{0};
std::atomic<int> sample_rate_events{0};
int __cdecl callback(int count, int status, float, void*) {
    if (count > 0) samples += count;
    if (count < 0 && status == 100) ++sample_rate_events;
    if (count < 0 && status == 101) ++lo_events;
    return 0;
}

int main() {
    std::fprintf(stderr, "loading\n"); std::fflush(stderr);
    HMODULE dll = LoadLibraryW(L"ExtIO_SDR_Bridge.dll");
    if (!dll) { std::fprintf(stderr, "LoadLibrary failed: %lu\n", GetLastError()); return 1; }
    auto init = reinterpret_cast<bool(__stdcall*)(char*, char*, int&)>(GetProcAddress(dll, "InitHW"));
    auto open = reinterpret_cast<bool(__stdcall*)()>(GetProcAddress(dll, "OpenHW"));
    auto close = reinterpret_cast<void(__stdcall*)()>(GetProcAddress(dll, "CloseHW"));
    auto set_cb = reinterpret_cast<void(__stdcall*)(int(__cdecl*)(int,int,float,void*))>(GetProcAddress(dll, "SetCallback"));
    auto start = reinterpret_cast<int(__stdcall*)(long)>(GetProcAddress(dll, "StartHW"));
    auto stop = reinterpret_cast<void(__stdcall*)()>(GetProcAddress(dll, "StopHW"));
    auto get_lo = reinterpret_cast<long(__stdcall*)()>(GetProcAddress(dll, "GetHWLO"));
    auto set_lo = reinterpret_cast<int(__stdcall*)(long)>(GetProcAddress(dll, "SetHWLO"));
    if (!init || !open || !close || !set_cb || !start || !stop || !get_lo || !set_lo) { std::fprintf(stderr, "Missing ExtIO export\n"); return 2; }
    std::fprintf(stderr, "exports ok\n"); std::fflush(stderr);
    char name[32]{}, model[32]{}; int type = 0;
    if (!init(name, model, type) || type != 3) return 3;
    std::fprintf(stderr, "init ok\n"); std::fflush(stderr);
    if (!open()) { std::fprintf(stderr, "OpenHW failed\n"); return 4; }
    std::fprintf(stderr, "open ok\n"); std::fflush(stderr);
    set_cb(callback); int block = start(144300000); if (block <= 0) return 5;
    std::fprintf(stderr, "start ok\n"); std::fflush(stderr);
    Sleep(3000); stop();
    const long frequency = get_lo();
    const int rejected_frequency = set_lo(frequency + 200000);
    close(); FreeLibrary(dll);
    char expected_text[32]{};
    const DWORD expected_length = GetEnvironmentVariableA("SDRBRIDGE_EXPECTED_FREQUENCY", expected_text, sizeof(expected_text));
    const long expected = expected_length > 0 && expected_length < sizeof(expected_text) ? std::strtol(expected_text, nullptr, 10) : frequency;
    std::printf("name=%s model=%s type=%d block=%d samples=%lld frequency=%ld rejected_frequency=%d lo_events=%d sample_rate_events=%d\n",
        name, model, type, block, samples.load(), frequency, rejected_frequency, lo_events.load(), sample_rate_events.load());
    if (samples.load() <= 1000000) return 6;
    if (lo_events.load() == 0 || sample_rate_events.load() == 0) return 7;
    if (frequency != expected) return 8;
    return rejected_frequency == frequency ? 0 : 9;
}
