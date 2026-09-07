add_executable(vfg-microbench src/main.cpp src/scalar.cpp)
target_compile_options(vfg-microbench PRIVATE -fno-fast-math -ffp-contract=off)
if(CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  set_source_files_properties(src/scalar.cpp PROPERTIES COMPILE_OPTIONS "-fno-vectorize;-fno-slp-vectorize")
elseif(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
  set_source_files_properties(src/scalar.cpp PROPERTIES COMPILE_OPTIONS "-fno-tree-vectorize")
endif()
add_test(NAME reduction_references COMMAND vfg-microbench --self-test)

