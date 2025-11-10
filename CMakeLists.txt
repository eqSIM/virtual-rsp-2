cmake_minimum_required(VERSION 3.23)

project(virtual-rsp
    VERSION 1.0.0
    DESCRIPTION "Virtual Remote SIM Provisioning - lpac with virtual eUICC"
    LANGUAGES C)

# Build lpac first (includes cJSON setup)
add_subdirectory(lpac)

# Build v-euicc daemon
add_subdirectory(v-euicc)

# Build tests (optional, can be disabled)
option(BUILD_TESTS "Build test suite" ON)
if(BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()

