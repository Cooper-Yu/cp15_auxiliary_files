cmake_minimum_required(VERSION 3.8)
project(rb1_ros2_description)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(gz_sim_vendor REQUIRED)
find_package(gz-sim8 REQUIRED)
add_library(rb1_elevator_startup_guard SHARED src/elevator_startup_guard.cpp)
target_link_libraries(rb1_elevator_startup_guard PRIVATE gz-sim8::gz-sim8)
target_compile_features(rb1_elevator_startup_guard PRIVATE cxx_std_17)
install(TARGETS rb1_elevator_startup_guard LIBRARY DESTINATION lib)
install(PROGRAMS scripts/elevator_startup.py scripts/elevator_command.py
  DESTINATION lib/${PROJECT_NAME})
# uncomment the following section in order to fill in
# further dependencies manually.
# find_package(<dependency> REQUIRED)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  # the following line skips the linter which checks for copyrights
  # uncomment the line when a copyright and license is not present in all source files
  #set(ament_cmake_copyright_FOUND TRUE)
  # the following line skips cpplint (only works in a git repo)
  # uncomment the line when this package is not in a git repo
  #set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

install(
  DIRECTORY
    launch
    meshes
    config
    urdf
    xacro
    worlds
  DESTINATION
    share/${PROJECT_NAME}/
)

ament_package()
