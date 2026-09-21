# RB-1 ROS 2 Control

Gazebo simulation of the RB-1 differential-drive base and elevator using
`ros2_control`. Simulation only; not for real hardware.

## 1. Install and build

Requires Ubuntu 24.04, ROS 2 Jazzy, Gazebo Harmonic, colcon and initialized rosdep.
For a new checkout only:

```bash
mkdir -p ~/ros2_ws/src
cd ~/ros2_ws/src
git clone -b jazzy https://github.com/Cooper-Yu/cp15_auxiliary_files.git
```

Install missing dependencies, then build:

```bash
source /opt/ros/jazzy/setup.bash
cd ~/ros2_ws
rosdep install --from-paths src/cp15_auxiliary_files --ignore-src --rosdistro jazzy
colcon build --packages-select robotnik_sensors rb1_ros2_description --executor sequential
source install/local_setup.bash
```

In every new terminal:

```bash
source /opt/ros/jazzy/setup.bash
source ~/ros2_ws/install/local_setup.bash
```

## 2. Start the simulation

Use the same entry point for both tasks; startup protection is included:

```bash
ros2 launch rb1_ros2_description rb1_ros2_xacro.launch.py
```

Run only one simulation. Wait for `RB1_ELEVATOR_READY` before sending commands.
This startup workaround avoids the known lower-limit sticking issue; use 1 mm,
not zero, as the lower target. Do not reset the world; restart the launch.
Cloud validation of this workaround is pending.

The elevator starts at 2 mm and is temporarily held there during controller
handoff, leaving clearance above the original 0 mm physical lower limit.
The 1 mm lowering target avoids returning to that limit, where sticking was
observed. These are experimentally verified simulation workaround values,
not hardware specifications or uniquely optimal settings.

## 3. Activate and check controllers

The launch automatically loads and activates all three controllers. In another
terminal, check:

```bash
ros2 node list
ros2 control list_controllers -c /controller_manager
ros2 control list_hardware_interfaces -c /controller_manager
ros2 topic info /rb1_base_controller/cmd_vel
ros2 topic info /rb1_elevator_controller/commands
```

Expected: `/controller_manager` and `/gz_ros_control` exist;
`joint_state_broadcaster`, `rb1_base_controller` and
`rb1_elevator_controller` are `active`. Both wheel `velocity` command
interfaces and `robot_elevator_platform_joint/position` are `claimed`.

If the elevator controller is loaded but inactive:

```bash
ros2 control set_controller_state rb1_elevator_controller active -c /controller_manager
```

## 4. Move and stop the base

With no other velocity publisher running, move forward, then explicitly stop:

```bash
ros2 topic pub --use-sim-time --rate 10 --times 20 /rb1_base_controller/cmd_vel geometry_msgs/msg/TwistStamped "{header: auto, twist: {linear: {x: 0.05}, angular: {z: 0.0}}}"
ros2 topic pub --use-sim-time --rate 10 --times 10 /rb1_base_controller/cmd_vel geometry_msgs/msg/TwistStamped "{header: auto, twist: {linear: {x: 0.0}, angular: {z: 0.0}}}"
```

## 5. Raise and lower the elevator

With the base stopped, raise to 20 mm, then lower to 1 mm:

```bash
ros2 run rb1_ros2_description elevator_command.py 0.02
sleep 10
ros2 topic echo /joint_states --once
ros2 run rb1_ros2_description elevator_command.py 0.001
sleep 10
ros2 topic echo /joint_states --once
```

The tool publishes `std_msgs/msg/Float64MultiArray` on
`/rb1_elevator_controller/commands`. Targets are absolute positions in metres.
Check the `position` entry matching `robot_elevator_platform_joint`: expect
approximately `0.02`, then `0.001`. Keep simulation running while waiting.
Stop the simulation with Ctrl+C when finished.

## Attribution

Adapted from Robotnik's BSD-licensed
[rb1_base_sim](https://github.com/RobotnikAutomation/rb1_base_sim),
[rb1_base_description](https://github.com/RobotnikAutomation/rb1_base_common/tree/melodic-devel/rb1_base_description)
and [robotnik_sensors](https://github.com/RobotnikAutomation/robotnik_sensors).
