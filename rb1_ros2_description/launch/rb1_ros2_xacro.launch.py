import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, RegisterEventHandler, TimerAction
from launch.event_handlers import OnProcessStart, OnProcessExit
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

    # This is to find the models inside the models folder in rb1_ros2_description package
    install_dir = get_package_prefix(description_package_name)
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

    rsp_robot = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        namespace=robot_name_1,
        parameters=[{'frame_prefix': robot_name_1 + '/', 'use_sim_time': use_sim_time,
                     'robot_description': ParameterValue(Command(['xacro ', robot_desc_path, ' robot_name:=', robot_name_1]), value_type=str)}],
        output="screen"
    )

    # Spawn the Robot #
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

    # ROS-Gazebo Bridge
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

    return LaunchDescription([
        gz_sim,
        rsp_robot,
        gz_spawn_entity,
        gz_bridge
    ])
