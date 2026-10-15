cmake_minimum_required(VERSION 3.20)

project(sdbu_source VERSION 0.1.1 LANGUAGES CXX)

if(NOT WIN32)
    message(FATAL_ERROR "This build currently targets the Windows SDR++ DLL installation.")
endif()

set(SDRPP_SOURCE_DIR "" CACHE PATH "SDR++ source tree matching the installed build")
set(SDRPP_INSTALL_DIR "" CACHE PATH "SDR++ installation containing sdrpp_core.dll")
set(SDRPP_IMPORT_LIBRARY "" CACHE FILEPATH "Generated sdrpp_core import library")
set(POTHOS_SDR_DIR "C:/Program Files/PothosSDR" CACHE PATH "PothosSDR installation")

foreach(required SDRPP_SOURCE_DIR SDRPP_INSTALL_DIR SDRPP_IMPORT_LIBRARY)
    if(NOT ${required})
        message(FATAL_ERROR "${required} is required")
    endif()
endforeach()

if(NOT EXISTS "${SDRPP_SOURCE_DIR}/core/src/module.h")
    message(FATAL_ERROR "SDRPP_SOURCE_DIR does not contain the expected SDR++ headers")
endif()
if(NOT EXISTS "${SDRPP_INSTALL_DIR}/sdrpp_core.dll")
    message(FATAL_ERROR "SDRPP_INSTALL_DIR does not contain sdrpp_core.dll")
endif()
if(NOT EXISTS "${SDRPP_IMPORT_LIBRARY}")
    message(FATAL_ERROR "SDRPP_IMPORT_LIBRARY does not exist")
endif()

add_library(sdrpp_core SHARED IMPORTED GLOBAL)
set_target_properties(sdrpp_core PROPERTIES
    IMPORTED_LOCATION "${SDRPP_INSTALL_DIR}/sdrpp_core.dll"
    IMPORTED_IMPLIB "${SDRPP_IMPORT_LIBRARY}"
)

add_library(sdbu_protocol STATIC
    src/sdbu_protocol.cpp
)
target_include_directories(sdbu_protocol PUBLIC include)
target_compile_features(sdbu_protocol PUBLIC cxx_std_17)

add_library(sdbu_source SHARED
    src/main.cpp
)
target_compile_features(sdbu_source PRIVATE cxx_std_17)
target_compile_definitions(sdbu_source PRIVATE
    NOMINMAX
    WIN32_LEAN_AND_MEAN
    _CRT_SECURE_NO_WARNINGS
)
target_include_directories(sdbu_source PRIVATE
    include
    "${SDRPP_SOURCE_DIR}/core/src"
    "${SDRPP_SOURCE_DIR}/core/src/imgui"
    "${POTHOS_SDR_DIR}/include"
)
target_link_libraries(sdbu_source PRIVATE
    sdbu_protocol
    sdrpp_core
    "${POTHOS_SDR_DIR}/lib/volk.lib"
    ws2_32
)
set_target_properties(sdbu_source PROPERTIES PREFIX "" OUTPUT_NAME "sdbu_source")

include(CTest)
if(BUILD_TESTING)
    add_executable(sdbu_protocol_tests tests/test_sdbu_protocol.cpp)
    target_compile_features(sdbu_protocol_tests PRIVATE cxx_std_17)
    target_link_libraries(sdbu_protocol_tests PRIVATE sdbu_protocol)
    add_test(NAME sdbu_protocol_tests COMMAND sdbu_protocol_tests)
endif()

install(TARGETS sdbu_source RUNTIME DESTINATION modules)
