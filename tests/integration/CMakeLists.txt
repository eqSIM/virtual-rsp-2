cmake_minimum_required(VERSION 3.23)

# Integration tests for full protocol flow
project(integration_tests LANGUAGES C)

# Find required packages
find_package(OpenSSL REQUIRED)

# Add integration test executable
add_executable(test_full_protocol test_full_protocol.c)

target_link_libraries(test_full_protocol PRIVATE
    OpenSSL::Crypto
)

# Add test to CTest
enable_testing()
add_test(NAME test_full_protocol COMMAND test_full_protocol)
