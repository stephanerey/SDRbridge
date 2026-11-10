cmake_minimum_required(VERSION 3.15)
project(SDRbridgeSoapyLMS7External CXX)

if(NOT DEFINED LIMESUITE_SOURCE_DIR)
    message(FATAL_ERROR "LIMESUITE_SOURCE_DIR is required")
endif()
if(NOT DEFINED LIMESUITE_INCLUDE_DIR)
    message(FATAL_ERROR "LIMESUITE_INCLUDE_DIR is required")
endif()
if(NOT DEFINED LIMESUITE_LIBRARY)
    message(FATAL_ERROR "LIMESUITE_LIBRARY is required")
endif()

find_package(SoapySDR CONFIG REQUIRED)

# LimeSuite's SoapyLMS7 subdirectory normally links to the LimeSuite target
# produced by the complete LimeSuite build. SDRbridge deliberately reuses the
# vendor SDK/runtime already installed by PothosSDR and only rebuilds the Soapy
# ABI boundary against its private SoapySDR 0.8 core.
add_library(LimeSuite SHARED IMPORTED GLOBAL)
set_target_properties(LimeSuite PROPERTIES
    IMPORTED_IMPLIB "${LIMESUITE_LIBRARY}"
    INTERFACE_INCLUDE_DIRECTORIES "${LIMESUITE_INCLUDE_DIR};${LIMESUITE_INCLUDE_DIR}/lime"
)

set(ENABLE_LIBRARY ON)
set(ENABLE_SOAPY_LMS7 ON)
add_subdirectory("${LIMESUITE_SOURCE_DIR}/SoapyLMS7" SoapyLMS7)
