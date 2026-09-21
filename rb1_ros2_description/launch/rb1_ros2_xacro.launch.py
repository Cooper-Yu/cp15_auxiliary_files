import os
import tempfile
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, RegisterEventHandler, EmitEvent
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
from ament_index_python.packages import get_package_prefix
from launch_ros.descriptions import ParameterValue


def generate_launch_description():

    description_package_name = "rb1_ros2_description"
    description_package_path = os.path.join(get_package_share_directory(
        "rb1_ros2_description"))
    gz_sim_pkg = get_package_share_directory("ros_gz_sim")
    sensors_pkg = get_package_share_directory("robotnik_sensors")

    # Make installed robot and sensor meshes discoverable by Gazebo.
    install_dir = get_package_prefix(description_package_name)
    # One private handoff directory per launch prevents stale release signals.
    guard_directory = tempfile.mkdtemp(prefix='rb1-elevator-guard-')
    guard_library = os.path.join(install_dir, 'lib', 'librb1_elevator_startup_guard.so')
    elevator_startup = Node(
        package=description_package_name, executable='elevator_startup.py',
        arguments=[guard_directory], output='screen')

    def startup_exited(event, context):
        # Never leave a partially initialized simulation running as if ready.
        if event.returncode != 0:
            return [EmitEvent(event=Shutdown(reason='Elevator startup guard failed'))]
        return []

    install_dir_sensors = get_package_prefix('robotnik_sensors')
    gazebo_models_path = os.path.join(description_package_path, 'meshes')
    sensor_models_path = os.path.join(sensors_pkg, 'meshes')
    if 'GZ_SIM_RESOURCE_PATH' in os.environ:
        os.environ['GZ_SIM_RESOURCE_PATH'] = os.environ['GZ_SIM_RESOURCE_PATH'] + \
            ':' + install_dir + '/share' + ':' + install_dir_sensors + '/share' + \
            ':' + gazebo_models_path + ':' + sensor_models_path
    else:
        os.environ['GZ_SIM_RESOURCE_PATH'] = install_dir + "/share" + ':' + \
            install_dir_sensors + "/share" + ':' + gazebo_models_path + ':' + sensor_models_path

    print("GZ_SIM_RESOURCE_PATH=="+str(os.environ["GZ_SIM_RESOURCE_PATH"]))

    # Use the clock bridged from Gazebo for simulated robot state.
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')

    # Setup to launch the simulator and Gazebo world
    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(gz_sim_pkg, 'launch', 'gz_sim.launch.py')),
            launch_arguments={'gz_args': [
            '-r ',  # <-- start unpaused
            PathJoinSubstitution([description_package_path, 'worlds', 'empty.world'])
        ]}.items(),
    )

    # Define the robot model files to be used
    robot_desc_file = "rb1_ros2_base.urdf.xacro"
    robot_desc_path = os.path.join(get_package_share_directory(
        "rb1_ros2_description"), "xacro", robot_desc_file)

    robot_name_1 = "rb1_robot"

    # Keep robot-specific description/TF names, but consume the broadcaster's
    # global /joint_states topic so moving wheel and lift transforms update.
    rsp_robot = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        namespace=robot_name_1,
        parameters=[{'frame_prefix': robot_name_1 + '/', 'use_sim_time': use_sim_time,
                     'robot_description': ParameterValue(Command([
                         'xacro ', robot_desc_path, ' robot_name:=', robot_name_1,
                         ' elevator_startup_guard:=true',
                         ' elevator_guard_dir:=', guard_directory,
                         ' elevator_guard_library:=', guard_library
                     ]), value_type=str)}],
        output="screen",
        remappings=[('joint_states', '/joint_states')],
    )

    # Spawn from the same description published by robot_state_publisher.
    gz_spawn_entity = Node(
        package="ros_gz_sim",
        executable="create",
        name="my_robot_spawn",
        arguments=[
            "-name", robot_name_1,
            "-allow_renaming", "true",
            "-topic", robot_name_1 + "/robot_description",
            "-x", "0.0",
            "-y", "0.0",
            "-z", "0.2",
        ],
        output="screen",
    )

    # Bridge simulation time and laser scans; control uses gz_ros2_control.
    gz_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="gz_bridge",
        arguments=[
            "/clock" + "@rosgraph_msgs/msg/Clock" + "[gz.msgs.Clock",
            "/hokuyo_ust20lx/hokuyo_ust20lx/scan" + "@sensor_msgs/msg/LaserScan" + "[gz.msgs.LaserScan",
        ],
        remappings=[
            ("/hokuyo_ust20lx/hokuyo_ust20lx/scan", "/scan"),
        ],
        output="screen",
    )

    # Gazebo creates /controller_manager; spawners connect to that manager.
    # Publish joint feedback for robot_state_publisher and inspection.
    joint_state_broadcaster_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[
            "joint_state_broadcaster",
            "--controller-manager", "/controller_manager"
        ],
        output="screen"
    )

    # Activate the differential-drive controller configured in the YAML file.
    rb1_base_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[
            "rb1_base_controller",
            "--controller-manager", "/controller_manager"
        ],
        output="screen"
    )

    # The lift and wheels claim different joints and can remain active together.
    rb1_elevator_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[
            "rb1_elevator_controller",
            "--controller-manager", "/controller_manager"
        ],
        output="screen"
    )

    return LaunchDescription([
        RegisterEventHandler(OnProcessExit(
            target_action=elevator_startup, on_exit=startup_exited)),
        gz_sim,
        rsp_robot,
        gz_spawn_entity,
        gz_bridge,
        joint_state_broadcaster_spawner,
        rb1_base_controller_spawner,
        rb1_elevator_controller_spawner,
        elevator_startup,
    ])
