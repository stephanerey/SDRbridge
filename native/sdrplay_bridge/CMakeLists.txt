cmake_minimum_required(VERSION 3.20)
project(sdrplay_bridge LANGUAGES CXX)
add_library(sdrplay_bridge SHARED sdrplay_bridge.cpp)
target_compile_features(sdrplay_bridge PRIVATE cxx_std_17)
target_compile_definitions(sdrplay_bridge PRIVATE WIN32_LEAN_AND_MEAN NOMINMAX)
target_include_directories(sdrplay_bridge PRIVATE "C:/Program Files/SDRplay/API/inc")
target_link_libraries(sdrplay_bridge PRIVATE "C:/Program Files/SDRplay/API/x64/sdrplay_api.lib")
set_target_properties(sdrplay_bridge PROPERTIES OUTPUT_NAME "sdrplay_bridge")
if (MSVC)
    # PyQt/Qt embarque un autre runtime MSVC ; le bridge garde son CRT
    # statique afin que std::mutex et les callbacks restent isolés.
    set_property(TARGET sdrplay_bridge PROPERTY MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
endif()

