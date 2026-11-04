cmake_minimum_required(VERSION 3.10)
project(g1_teleop LANGUAGES CXX)

find_package(ament_cmake REQUIRED)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(dex3_motion INTERFACE)
target_include_directories(dex3_motion INTERFACE
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)

set(UNITREE_SDK2_DIR "$ENV{UNITREE_SDK2_DIR}" CACHE PATH
  "Path to the official unitree_sdk2 source tree")
if(NOT UNITREE_SDK2_DIR)
  get_filename_component(UNITREE_SDK2_DIR
    "${CMAKE_CURRENT_SOURCE_DIR}/../../third_party/unitree_sdk2" ABSOLUTE)
  set(UNITREE_SDK2_DIR "${UNITREE_SDK2_DIR}" CACHE PATH
    "Path to the official unitree_sdk2 source tree" FORCE)
endif()
option(G1_TELEOP_BUILD_HARDWARE "Build native SDK2 hardware executables" ON)

if(G1_TELEOP_BUILD_HARDWARE AND EXISTS "${UNITREE_SDK2_DIR}/CMakeLists.txt")
  set(BUILD_EXAMPLES OFF CACHE BOOL "Build Unitree SDK2 examples" FORCE)
  add_subdirectory("${UNITREE_SDK2_DIR}" unitree_sdk2 EXCLUDE_FROM_ALL)

  add_executable(dex3_smoke_native src/dex3_smoke.cpp)
  target_link_libraries(dex3_smoke_native PRIVATE dex3_motion unitree_sdk2)
  target_compile_options(dex3_smoke_native PRIVATE -Wall -Wextra -Wpedantic)
  set_target_properties(dex3_smoke_native PROPERTIES
    BUILD_RPATH "${UNITREE_SDK2_DIR}/thirdparty/lib/${CMAKE_SYSTEM_PROCESSOR}"
    INSTALL_RPATH "$ORIGIN")
  install(TARGETS dex3_smoke_native DESTINATION lib/${PROJECT_NAME})
  install(PROGRAMS scripts/dex3_smoke DESTINATION lib/${PROJECT_NAME})
  install(FILES
    "${UNITREE_SDK2_DIR}/thirdparty/lib/${CMAKE_SYSTEM_PROCESSOR}/libddsc.so"
    "${UNITREE_SDK2_DIR}/thirdparty/lib/${CMAKE_SYSTEM_PROCESSOR}/libddsc.so.0"
    "${UNITREE_SDK2_DIR}/thirdparty/lib/${CMAKE_SYSTEM_PROCESSOR}/libddscxx.so"
    "${UNITREE_SDK2_DIR}/thirdparty/lib/${CMAKE_SYSTEM_PROCESSOR}/libddscxx.so.0"
    DESTINATION lib/${PROJECT_NAME})
  message(STATUS "g1_teleop: building native Dex3 hardware smoke test")
else()
  message(WARNING
    "g1_teleop: UNITREE_SDK2_DIR is not an official SDK2 source tree; "
    "building tests and headers only. The dex3_smoke hardware executable "
    "will not be installed.")
endif()

install(DIRECTORY include/ DESTINATION include)
install(DIRECTORY config DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(test_dex3_motion test/test_dex3_motion.cpp)
  target_link_libraries(test_dex3_motion dex3_motion)
endif()

ament_export_include_directories(include)
ament_package()
