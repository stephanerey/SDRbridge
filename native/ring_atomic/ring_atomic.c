#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>

#ifdef SDB_RING_ATOMIC_EXPORTS
#define SDB_API __declspec(dllexport)
#else
#define SDB_API __declspec(dllimport)
#endif

SDB_API uint32_t __cdecl sdb_guard_load(const volatile LONG *address) {
    return (uint32_t)InterlockedCompareExchange((volatile LONG *)address, 0, 0);
}

SDB_API void __cdecl sdb_guard_store(volatile LONG *address, uint32_t value) {
    MemoryBarrier();
    InterlockedExchange(address, (LONG)value);
    MemoryBarrier();
}

SDB_API void __cdecl sdb_full_barrier(void) {
    MemoryBarrier();
}
