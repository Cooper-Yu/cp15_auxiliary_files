"""Opt-in startup protection for the Jazzy/Harmonic RB-1 simulation."""
import os
import tempfile
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, RegisterEventHandler, EmitEvent
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory, get_package_prefix


def generate_launch_description():
    package = 'rb1_ros2_description'
    # Unique, mode-0700 directory prevents stale release signals across launches.
    directory = tempfile.mkdtemp(prefix='rb1-elevator-guard-')
    coordinator = Node(
        package=package, executable='elevator_startup.py',
        arguments=[directory], output='screen')

    def exited(event, context):
        if event.returncode != 0:
            return [EmitEvent(event=Shutdown(reason='Elevator startup guard failed'))]
        return []

    return LaunchDescription([
        RegisterEventHandler(OnProcessExit(target_action=coordinator, on_exit=exited)),
        IncludeLaunchDescription(PythonLaunchDescriptionSource(os.path.join(
            get_package_share_directory(package), 'launch', 'rb1_ros2_xacro.launch.py')),
            launch_arguments={
                'elevator_startup_guard': 'true',
                'elevator_guard_dir': directory,
                'elevator_guard_library': os.path.join(
                    get_package_prefix(package), 'lib', 'librb1_elevator_startup_guard.so'),
            }.items()),
        coordinator,
    ])
