cmake_minimum_required(VERSION 3.23)

project(v-euicc-tests
    VERSION 1.0.0
    DESCRIPTION "Tests for Virtual eUICC with PQC support"
    LANGUAGES C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Enable testing
enable_testing()

# Add subdirectories
add_subdirectory(unit)
add_subdirectory(integration)

