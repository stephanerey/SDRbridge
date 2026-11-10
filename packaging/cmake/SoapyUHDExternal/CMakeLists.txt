cmake_minimum_required(VERSION 3.15)
project(SDRbridgeSoapyUHDExternal CXX)

foreach(required SOAPYUHD_SOURCE_DIR UHD_INCLUDE_DIR UHD_LIBRARY BOOST_INCLUDE_DIR)
    if(NOT DEFINED ${required})
        message(FATAL_ERROR "${required} is required")
    endif()
endforeach()

find_package(SoapySDR CONFIG REQUIRED)

# Build only the Soapy-to-UHD RX module. The inverse UHD-to-Soapy adapter is
# intentionally omitted: SDRbridge owns the receiver and never exposes a UHD
# device or a transmit path. UHD headers are staged without Pothos' Soapy 0.8
# headers, keeping this module on SDRbridge's private Soapy 0.8 ABI.
SOAPY_SDR_MODULE_UTIL(
    TARGET uhdSupport
    SOURCES "${SOAPYUHD_SOURCE_DIR}/SoapyUHDDevice.cpp"
    LIBRARIES "${UHD_LIBRARY}"
)
target_include_directories(uhdSupport PRIVATE
    "${SOAPYUHD_SOURCE_DIR}"
    "${UHD_INCLUDE_DIR}"
    "${BOOST_INCLUDE_DIR}"
)
target_compile_features(uhdSupport PRIVATE cxx_std_17)
target_compile_definitions(uhdSupport PRIVATE BOOST_ALL_DYN_LINK)
