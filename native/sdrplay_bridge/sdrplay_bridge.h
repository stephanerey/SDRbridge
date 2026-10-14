#pragma once
#include <stdint.h>

#ifdef SDRPLAY_BRIDGE_EXPORTS
#define SDB_API __declspec(dllexport)
#else
#define SDB_API __declspec(dllimport)
#endif

extern "C" {
typedef void(__cdecl* sdb_iq_callback)(const int16_t* interleaved_iq, uint32_t sample_count, uint64_t first_sample, void* context);

SDB_API int __cdecl sdb_open(double sample_rate_hz, double frequency_hz, int bandwidth_khz,
                              int gain_reduction_db, int agc_enabled,
                              sdb_iq_callback callback, void* context);
SDB_API int __cdecl sdb_close(void);
// Lit un bloc produit par le callback SDRplay sans rappeler Python depuis le
// thread du driver. Retourne 1 si un bloc est disponible, 0 sur timeout et une
// valeur négative en cas d'arrêt/erreur.
SDB_API int __cdecl sdb_read_iq(int16_t* interleaved_iq, uint32_t capacity_samples,
                               uint32_t* sample_count, uint64_t* first_sample,
                               int timeout_ms);
SDB_API int __cdecl sdb_set_frequency(double frequency_hz);
SDB_API int __cdecl sdb_set_gain(int gain_reduction_db, int agc_enabled);
SDB_API int __cdecl sdb_set_bandwidth(int bandwidth_khz);
SDB_API int __cdecl sdb_set_options(int antenna, int bias_t, int rf_notch, int rf_dab_notch, int hdr_enable, int hdr_bw, int lna_state, int if_type);
SDB_API const char* __cdecl sdb_last_error(void);
SDB_API const char* __cdecl sdb_serial(void);
SDB_API int __cdecl sdb_hardware_version(void);
SDB_API float __cdecl sdb_api_version(void);
}

