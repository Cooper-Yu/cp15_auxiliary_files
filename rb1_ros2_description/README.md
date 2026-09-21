# RB-1 ROS 2 Control simulation

This package spawns Robotnik's RB-1 in Gazebo Sim and uses `gz_ros2_control`
to control its differential-drive wheels and lifting platform. One controller
manager owns the simulated hardware; three controllers are started automatically.
The commands below are for simulation only, not real hardware.

## 1. Requirements and installation

Use Ubuntu 24.04, ROS 2 Jazzy and Gazebo Sim 8 (Harmonic). Run commands in Linux
or WSL, with a graphical desktop available for Gazebo. Keep the workspace in the
Linux filesystem. The Construct Jazzy environment can use the same instructions.

Required ROS packages include `xacro`, `robot_state_publisher`, `ros_gz_sim`,
`ros_gz_bridge`, `controller_manager`, `gz_ros2_control`,
`joint_state_broadcaster`, `diff_drive_controller` and `position_controllers`.
`robotnik_sensors` is included in this repository. `colcon`, `rosdep`, Git and
the ROS CLI tools are also needed. `teleop_twist_keyboard` is optional for
keyboard control. On an already configured course environment, first check the
installed packages instead of upgrading the environment unnecessarily:

```bash
source /opt/ros/jazzy/setup.bash
ros2 pkg prefix gz_ros2_control
ros2 pkg prefix diff_drive_controller
ros2 pkg prefix position_controllers
gz sim --versions
```

For a fresh workspace only (do not clone a second copy into an existing package):

```bash
mkdir -p ~/ros2_ws/src
cd ~/ros2_ws/src
git clone -b jazzy https://github.com/Cooper-Yu/cp15_auxiliary_files.git
```

If dependencies are missing, and rosdep is already initialized, install the
declared dependencies. This step changes installed system packages; review its
proposed changes before accepting them. It is not required when all dependencies
are already installed.

```bash
source /opt/ros/jazzy/setup.bash
rosdep update
rosdep install --from-paths ~/ros2_ws/src/cp15_auxiliary_files --ignore-src --rosdistro jazzy
```

Build the two packages (no unrelated workspace packages are needed):

<!-- command: build -->
```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
timeout --signal=INT --kill-after=10s 180s colcon build --base-paths src/cp15_auxiliary_files --packages-select robotnik_sensors rb1_ros2_description --executor sequential
source ~/ros2_ws/install/local_setup.bash
```

Run these two source commands in **every new terminal**:

<!-- command: environment -->
```bash
source /opt/ros/jazzy/setup.bash
source ~/ros2_ws/install/local_setup.bash
```

## 2. Start the simulation

In terminal A, after sourcing the environment:

<!-- command: launch -->
```bash
ros2 launch rb1_ros2_description rb1_ros2_xacro.launch.py
```

Keep this terminal running. Gazebo should show `rb1_robot` in an empty world.
Run only one instance and do not run a keyboard/velocity publisher concurrently
with the tests below. The launch starts Gazebo unpaused and bridges `/clock`.
After changing the model, rebuild and restart the simulation; editing an Xacro
does not update an already spawned robot.

## 3. Check controller activation

In terminal B, after sourcing the environment, wait for startup and run:

<!-- command: status -->
```bash
ros2 node list
ros2 control list_controllers -c /controller_manager
ros2 control list_hardware_interfaces -c /controller_manager
ros2 topic info /rb1_base_controller/cmd_vel --verbose
ros2 topic info /rb1_elevator_controller/commands --verbose
timeout --signal=INT 10s ros2 topic echo /clock --once
```

Expected nodes include `/controller_manager` and `/gz_ros_control`.
Expected controllers are all `active`:

| Controller | Type | Claimed command interfaces |
|---|---|---|
| `joint_state_broadcaster` | `joint_state_broadcaster/JointStateBroadcaster` | None; publishes state |
| `rb1_base_controller` | `diff_drive_controller/DiffDriveController` | Left/right wheel `velocity` |
| `rb1_elevator_controller` | `position_controllers/JointGroupPositionController` | `robot_elevator_platform_joint/position` |

The launch already loads and activates them. Do not start a second controller
manager or repeatedly spawn controllers that are already active. If a controller
was loaded but is `inactive`, activate that controller explicitly; for example:

```bash
ros2 control set_controller_state rb1_elevator_controller active -c /controller_manager
```

If it is absent from the controller list, and no spawner is still running, load
and activate it using the existing manager configuration:

```bash
ros2 run controller_manager spawner rb1_elevator_controller -c /controller_manager --controller-manager-timeout 60 --switch-timeout 30
```

Initial service waits are possible during startup. If a spawner reports a timeout,
query the **current** state before retrying: a prior error does not necessarily
describe the final controller state. Do not send motion commands until all three
controllers are active and the simulation clock is advancing.

## 4. Drive and stop the base

The input is `/rb1_base_controller/cmd_vel`, type
`geometry_msgs/msg/TwistStamped`. Use simulation time and `header: auto` so each
message has a current timestamp; a fixed zero timestamp can be stale.

First record the starting odometry:

<!-- command: odom -->
```bash
timeout --signal=INT 10s ros2 topic echo /rb1_base_controller/odom --once
```

Send 20 low-speed commands at 10 Hz (about two seconds of publishing):

<!-- command: forward -->
```bash
timeout --signal=INT --kill-after=2s 15s ros2 topic pub --use-sim-time --rate 10 --times 20 /rb1_base_controller/cmd_vel geometry_msgs/msg/TwistStamped "{header: auto, twist: {linear: {x: 0.05}, angular: {z: 0.0}}}"
```

Then explicitly stop the base:

<!-- command: stop -->
```bash
timeout --signal=INT --kill-after=2s 10s ros2 topic pub --use-sim-time --rate 10 --times 10 /rb1_base_controller/cmd_vel geometry_msgs/msg/TwistStamped "{header: auto, twist: {linear: {x: 0.0}, angular: {z: 0.0}}}"
```

Repeat the odometry command. Expect forward displacement and near-zero final
`twist.twist.linear.x` and `angular.z`. The distance is approximately 0.1 m;
CLI discovery latency, the command timeout and simulation speed can affect it.
The configured controller's default `cmd_vel_timeout` is 0.5 s in the tested
environment, but always send an explicit stop rather than relying on it.

Optional keyboard control, in place of the terminal publisher:

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -p stamped:=true -p use_sim_time:=true -p speed:=0.05 -r cmd_vel:=/rb1_base_controller/cmd_vel
```

Keep that terminal focused, follow its key help (`i` forward, `k` stop), and exit
the keyboard program before another publisher is started. Keyboard-repeat and
controller timeout behavior may also make the robot stop after a key is released.

## 5. Raise and lower the platform

The input is `/rb1_elevator_controller/commands`, type
`std_msgs/msg/Float64MultiArray`. The single array entry is the **absolute joint
position in metres**, not a speed or an increment. Valid travel is `0.0` to
`0.034` m. Do not command outside this range or rely on command-limit enforcement.

With the base stopped, read the initial position:

<!-- command: joints -->
```bash
timeout --signal=INT 10s ros2 topic echo /joint_states --once
```

Find `robot_elevator_platform_joint` in `name` and read the corresponding entry
in `position`; do not assume array ordering. Raise to 2 cm:

<!-- command: lift_up -->
```bash
timeout --signal=INT --kill-after=2s 15s ros2 topic pub --rate 10 --times 20 --keep-alive 1 /rb1_elevator_controller/commands std_msgs/msg/Float64MultiArray "{data: [0.02]}"
```

Allow time to approach the target and read feedback:

<!-- command: lift_feedback -->
```bash
sleep 10
timeout --signal=INT 10s ros2 topic echo /joint_states --once
```

Expect approximately `0.02` m. On a slow or paused simulation, wall-clock waiting
does not guarantee simulation time advances: check `/clock` and observe longer
if needed. Repeating `[0.02]` does not accumulate height. Publishing ending does
not cancel a position target or automatically lower the platform.

Lower back to the initial position:

<!-- command: lift_down -->
```bash
timeout --signal=INT --kill-after=2s 15s ros2 topic pub --rate 10 --times 20 --keep-alive 1 /rb1_elevator_controller/commands std_msgs/msg/Float64MultiArray "{data: [0.0]}"
```

Run the same feedback block again; expect a position near `0.0` m. The lift exports
only position feedback, so `nan` in its velocity/effort fields is not itself a
failure. No extra service or action is required for this topic-based controller.

## 6. Shutdown and troubleshooting

Stop any keyboard or command publisher. Send the base stop command above while
the simulation is still running. In terminal A press Ctrl+C and wait for Gazebo
and the launch processes to exit before starting another instance.

If a command is published but the lift stays at zero, inspect the internal goal:

```bash
timeout --signal=INT 10s ros2 topic echo /controller_manager/introspection_data/full --once
```

Compare `command_interface.robot_elevator_platform_joint/position` with the
matching `state_interface` value. A goal of 0.02 with feedback near zero is
different from a missing subscriber or an inactive controller. Verify installed
model files, the loaded package prefix, advancing time and unique simulation
before changing dependencies.

The platform model includes a **simulation workaround**: mass `0.5 kg` and an
inertial origin at the platform link origin. Controlled local tests found that
both changes together restore lift motion; changing either alone did not. The
original inertia tensor is retained to keep this repair isolated. These are not
measured hardware parameters, and physically calibrated dynamics remain future
work. This does not establish a specific Gazebo/DART implementation bug.

## 7. Update an existing The Construct checkout

Stop its old simulation first. Save any local work before updating; do not reset
or discard changes. Check `git status --short` is empty and the branch is `jazzy`:

```bash
cd ~/ros2_ws/src/cp15_auxiliary_files
git status --short
git branch --show-current
git pull --ff-only https://github.com/Cooper-Yu/cp15_auxiliary_files.git jazzy
git log -1 --oneline
```

If the worktree is dirty, the branch differs, or fast-forward fails, stop and
resolve that state instead of forcing the update. Rebuild with section 1, source
the overlay in both terminals, restart with section 2, and execute sections 3–5.
Verify both the base and lift on the same updated revision.

## Verification scope

### Important: delayed restart from zero remains unreliable

The earlier short up/down test below did not cover a long dwell at zero.
Later local and cloud tests reproduced failure to rise after settling on the
lower limit, despite an accepted nonzero command. Do not treat those earlier
results as a complete repair.

### Optional guarded simulation startup

This opt-in **simulation-only workaround** starts the lift at 2 mm and temporarily
locks its simulated position limits. A bounded coordinator verifies active
controllers, the claimed position interface, a unique command subscriber,
fresh feedback and the internal 2 mm command. It then restores the original
0–34 mm limits gradually over one simulation second. After release the plugin
stops writing limits. Failure shuts down this launch instead of reporting ready.
The default `rb1_ros2_xacro.launch.py` remains unchanged in behavior.

The package now builds a Gazebo Harmonic plugin and requires the Jazzy
`gz_sim_vendor` development environment, plus `rclpy`,
`controller_manager_msgs`, `std_msgs` and Python YAML. Rebuild the package:

```bash
source /opt/ros/jazzy/setup.bash
cd ~/ros2_ws
colcon build --packages-select robotnik_sensors rb1_ros2_description --executor sequential
source ~/ros2_ws/install/local_setup.bash
ros2 launch rb1_ros2_description rb1_guarded_sim.launch.py
```

Stop any older simulation first. Wait for `RB1_ELEVATOR_READY` before issuing
commands. In another terminal with the same ROS environment:

```bash
source /opt/ros/jazzy/setup.bash
source ~/ros2_ws/install/local_setup.bash
ros2 run rb1_ros2_description elevator_command.py 0.02
sleep 10
timeout --signal=INT 10s ros2 topic echo /joint_states --once
ros2 run rb1_ros2_description elevator_command.py 0.001
sleep 20
timeout --signal=INT 10s ros2 topic echo /joint_states --once
ros2 run rb1_ros2_description elevator_command.py 0.02
sleep 10
timeout --signal=INT 10s ros2 topic echo /joint_states --once
```

Read the position corresponding to `robot_elevator_platform_joint`, not an
assumed array index. Expected values are near 0.02, 0.001, then 0.02 m.
The command utility rejects nonfinite values and targets outside 1–34 mm;
it does not silently convert zero to 1 mm and does not prove motion succeeded.
Direct publishing to the controller bypasses this check. **Do not send zero in
this workaround workflow**, including the older down-command example.
Do not reset the world during a guarded run: protection is one-shot; restart
the launch for a new trial. Private `/tmp/rb1-elevator-guard-*` folders retain
small handoff logs for diagnosis.

This changes the usable low position to 1 mm, not the physical URDF limit.
It does not repair the zero-limit behavior, validate real hardware dynamics,
justify reverting the mass/COM change, or establish cloud grading acceptance.
Base motion/stop commands remain those in the earlier sections.

Local package validation on 2026-09-21: guarded startup plus three positive-low
cycles passed. A second fresh launch exercised the installed command utility:
0.019999977 m → 0.000999999991 m (after a 20-second wall wait) →
0.019999976 m. The base then moved 0.100 m and stopped with zero-speed feedback.
Static checks confirmed that the default expanded model is unchanged and
invalid targets (zero, negative, above 34 mm, NaN and infinity) are rejected.
The 34 mm upper endpoint was not retested in this guarded workflow.
Cloud validation of this new optional entry point is still pending.

Local reference environment: Ubuntu 24.04/WSL, Jazzy, Gazebo Sim 8.11.0,
`gz_ros2_control` 1.2.20. The model has passed base forward/stop tests and lift
targets 0.02, 0.034 and 0.0 m, including TF feedback. The Construct previously
reported plugin 1.2.17; repair validation there is still pending. Local success
is not a claim of cloud grading success or hardware validation.

On 2026-09-21, the build, launch, status, forward/stop and lift up/down code blocks
in this README were also executed directly in that local environment. The base
moved 0.115 m and stopped; lift feedback reached 0.019999991 m and returned to
0.0000000097 m. Optional dependency installation, keyboard and manual controller
recovery branches were not rerun as part of that command-by-command test.

## Attribution

This package modifies/adapts files from:

- [RobotnikAutomation/rb1_base_sim](https://github.com/RobotnikAutomation/rb1_base_sim), BSD 2-Clause License.
- [RobotnikAutomation/rb1_base_common/rb1_base_description](https://github.com/RobotnikAutomation/rb1_base_common/tree/melodic-devel/rb1_base_description), BSD License.
- [RobotnikAutomation/robotnik_sensors](https://github.com/RobotnikAutomation/robotnik_sensors), BSD License.
