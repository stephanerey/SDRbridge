#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <atomic>
#include <cstdio>

std::atomic<long long> samples{0};
int __cdecl callback(int count, int, float, void*) { if (count > 0) samples += count; return 0; }

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
    if (!init || !open || !close || !set_cb || !start || !stop) { std::fprintf(stderr, "Missing ExtIO export\n"); return 2; }
    std::fprintf(stderr, "exports ok\n"); std::fflush(stderr);
    char name[32]{}, model[32]{}; int type = 0;
    if (!init(name, model, type) || type != 3) return 3;
    std::fprintf(stderr, "init ok\n"); std::fflush(stderr);
    if (!open()) { std::fprintf(stderr, "OpenHW failed\n"); return 4; }
    std::fprintf(stderr, "open ok\n"); std::fflush(stderr);
    set_cb(callback); int block = start(144300000); if (block <= 0) return 5;
    std::fprintf(stderr, "start ok\n"); std::fflush(stderr);
    Sleep(3000); stop(); close(); FreeLibrary(dll);
    std::printf("name=%s model=%s type=%d block=%d samples=%lld\n", name, model, type, block, samples.load());
    return samples.load() > 1000000 ? 0 : 6;
}
