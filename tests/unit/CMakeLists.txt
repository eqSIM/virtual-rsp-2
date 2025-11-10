# Unit tests for PQC crypto primitives

# Include parent directories for headers
include_directories(${CMAKE_SOURCE_DIR}/v-euicc/include)
include_directories(${CMAKE_SOURCE_DIR})

# Find dependencies
find_package(OpenSSL REQUIRED)

# Check for liboqs (optional for unit tests)
if(ENABLE_PQC)
    find_package(PkgConfig REQUIRED)
    pkg_check_modules(LIBOQS liboqs)
    
    if(LIBOQS_FOUND)
        include_directories(${LIBOQS_INCLUDE_DIRS})
        link_directories(${LIBOQS_LIBRARY_DIRS})
        
        # ML-KEM unit test (includes crypto.c for the implementation)
        add_executable(test_mlkem test_mlkem.c ${CMAKE_SOURCE_DIR}/v-euicc/src/crypto.c)
        target_compile_definitions(test_mlkem PRIVATE ENABLE_PQC)
        target_link_libraries(test_mlkem PRIVATE ${LIBOQS_LIBRARIES} OpenSSL::Crypto)
        add_test(NAME test_mlkem COMMAND test_mlkem)
        
        # Hybrid KDF unit test (includes crypto.c for the implementation)
        add_executable(test_hybrid_kdf test_hybrid_kdf.c ${CMAKE_SOURCE_DIR}/v-euicc/src/crypto.c)
        target_compile_definitions(test_hybrid_kdf PRIVATE ENABLE_PQC)
        target_link_libraries(test_hybrid_kdf PRIVATE ${LIBOQS_LIBRARIES} OpenSSL::Crypto)
        add_test(NAME test_hybrid_kdf COMMAND test_hybrid_kdf)
        
        # ML-KEM verbose test - proves real algorithms with detailed logging
        add_executable(test_mlkem_verbose test_mlkem_verbose.c ${CMAKE_SOURCE_DIR}/v-euicc/src/crypto.c)
        target_compile_definitions(test_mlkem_verbose PRIVATE ENABLE_PQC)
        target_link_libraries(test_mlkem_verbose PRIVATE ${LIBOQS_LIBRARIES} OpenSSL::Crypto)
        add_test(NAME test_mlkem_verbose COMMAND test_mlkem_verbose)
    endif()
endif()

