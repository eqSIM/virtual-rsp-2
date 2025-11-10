cmake_minimum_required(VERSION 3.23)

project(v-euicc
    VERSION 1.0.0
    DESCRIPTION "Virtual eUICC daemon for lpac"
    LANGUAGES C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Option to enable Post-Quantum Cryptography support
option(ENABLE_PQC "Enable Post-Quantum Cryptography support" ON)

# Use cJSON from parent lpac project
if (NOT TARGET cjson)
    message(FATAL_ERROR "cJSON not available. Build from root CMakeLists.txt or set USE_SYSTEM_DEPS=ON")
endif()

# Include directories
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/include)
include_directories(${CMAKE_SOURCE_DIR}/lpac/euicc)
include_directories(${CMAKE_SOURCE_DIR})

# Find OpenSSL for ECDSA signing
find_package(OpenSSL REQUIRED)

# Find liboqs for PQC support (before creating target)
if(ENABLE_PQC)
    find_package(PkgConfig REQUIRED)
    pkg_check_modules(LIBOQS liboqs)
    
    if(LIBOQS_FOUND)
        message(STATUS "liboqs found: ${LIBOQS_VERSION}")
        include_directories(${LIBOQS_INCLUDE_DIRS})
        link_directories(${LIBOQS_LIBRARY_DIRS})
    else()
        message(WARNING "liboqs not found, PQC support disabled")
    endif()
endif()

add_executable(v-euicc-daemon
    src/main.c
    src/protocol.c
    src/euicc_state.c
    src/apdu_handler.c
    src/cert_loader.c
    src/crypto.c
    ../logging.c
)

# Link libraries
if(ENABLE_PQC AND LIBOQS_FOUND)
    target_compile_definitions(v-euicc-daemon PRIVATE ENABLE_PQC)
    target_link_libraries(v-euicc-daemon PRIVATE cjson euicc OpenSSL::Crypto ${LIBOQS_LIBRARIES})
else()
    target_link_libraries(v-euicc-daemon PRIVATE cjson euicc OpenSSL::Crypto)
endif()

if(WIN32)
    target_link_libraries(v-euicc-daemon PRIVATE ws2_32)
endif()

# Installation
install(TARGETS v-euicc-daemon RUNTIME DESTINATION bin)

