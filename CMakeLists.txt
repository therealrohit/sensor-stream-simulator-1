cmake_minimum_required(VERSION 3.20)
project(sensor_stream_simulator_cpp VERSION 0.1.0 LANGUAGES CXX)

find_package(Threads REQUIRED)
add_library(sensor_stream cpp/sensor_stream.cpp)
target_include_directories(sensor_stream PUBLIC cpp)
target_compile_features(sensor_stream PUBLIC cxx_std_20)
set_target_properties(sensor_stream PROPERTIES CXX_EXTENSIONS OFF)
target_link_libraries(sensor_stream PUBLIC Threads::Threads)
if(CMAKE_CXX_COMPILER_ID MATCHES "Clang|GNU")
  target_compile_options(sensor_stream PUBLIC -Wall -Wextra -Wpedantic)
endif()

add_executable(sensor_simulator cpp/main.cpp)
target_link_libraries(sensor_simulator PRIVATE sensor_stream)

include(CTest)
if(BUILD_TESTING)
  add_executable(sensor_stream_tests cpp/tests.cpp)
  target_link_libraries(sensor_stream_tests PRIVATE sensor_stream)
  add_test(NAME sensor_stream_tests COMMAND sensor_stream_tests)
  add_test(NAME cli_smoke COMMAND sensor_simulator --frames 1000 --capacity 4)
  set_tests_properties(cli_smoke PROPERTIES PASS_REGULAR_EXPRESSION
    "produced=1000 enqueued=1000 consumed=1000 dropped=0")
  add_test(NAME cli_invalid_capacity COMMAND sensor_simulator --capacity 0)
  add_test(NAME cli_invalid_number COMMAND sensor_simulator --frames -1)
  add_test(NAME cli_unknown_option COMMAND sensor_simulator --unknown 1)
  set_tests_properties(cli_invalid_capacity cli_invalid_number cli_unknown_option
    PROPERTIES WILL_FAIL TRUE)
  set_tests_properties(sensor_stream_tests cli_smoke cli_invalid_capacity
    cli_invalid_number cli_unknown_option PROPERTIES TIMEOUT 20)
endif()
