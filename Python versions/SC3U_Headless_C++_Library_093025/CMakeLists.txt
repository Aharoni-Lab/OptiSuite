# CMakeLists.txt for SC3U_Headless library
cmake_minimum_required(VERSION 3.12)
project(SC3U_Headless)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Create the library
add_library(sc3u_headless SHARED
    SC3U_Headless.cpp
    SC3U_Headless.h
)

# Set output directory
set_target_properties(sc3u_headless PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib
    ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib
)

# Platform-specific libraries
if(WIN32)
    target_link_libraries(sc3u_headless)
else()
    target_link_libraries(sc3u_headless pthread)
endif()

# Python binding (optional)
option(BUILD_PYTHON_BINDING "Build Python binding" OFF)

if(BUILD_PYTHON_BINDING)
    find_package(pybind11 REQUIRED)
    
    pybind11_add_module(sc3u_headless_python
        SC3U_Headless.cpp
    )
    
    target_compile_definitions(sc3u_headless_python PRIVATE PYBIND11_MODULE)
    
    if(WIN32)
        target_link_libraries(sc3u_headless_python)
    else()
        target_link_libraries(sc3u_headless_python pthread)
    endif()
endif()

# Installation
install(TARGETS sc3u_headless
    RUNTIME DESTINATION bin
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
)

install(FILES SC3U_Headless.h
    DESTINATION include
)
