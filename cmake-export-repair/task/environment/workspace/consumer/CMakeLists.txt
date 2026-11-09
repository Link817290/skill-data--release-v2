cmake_minimum_required(VERSION 3.10)
project(cjson_export_consumer C)

find_package(cJSON CONFIG REQUIRED)

add_executable(smoke main.c)
target_link_libraries(smoke PRIVATE cjson_utils-static)
