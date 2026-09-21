#!/usr/bin/env python3
"""Bounded simulation handoff: readiness, internal target, release, feedback."""
import math
from pathlib import Path
import subprocess
import sys
import time
import yaml
import rclpy
from rclpy.qos import qos_profile_sensor_data
from controller_manager_msgs.srv import ListControllers, ListHardwareInterfaces
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray


def main():
    directory = Path(sys.argv[1])
    rclpy.init()
    node = rclpy.create_node('rb1_elevator_startup')
    state = {}
    joint = 'robot_elevator_platform_joint'
    topic = '/rb1_elevator_controller/commands'

    def receive(msg):
        if joint in msg.name:
            index = msg.name.index(joint)
            if index < len(msg.position):
                state.update(q=msg.position[index], wall=time.monotonic(),
                             sim=msg.header.stamp.sec + msg.header.stamp.nanosec / 1e9)

    node.create_subscription(JointState, '/joint_states', receive, qos_profile_sensor_data)
    pub = node.create_publisher(Float64MultiArray, topic, 10)
    controllers = node.create_client(ListControllers, '/controller_manager/list_controllers')
    hardware = node.create_client(ListHardwareInterfaces, '/controller_manager/list_hardware_interfaces')

    def request(client, request_type):
        if not client.wait_for_service(timeout_sec=0.5):
            return None
        future = client.call_async(request_type())
        rclpy.spin_until_future_complete(node, future, timeout_sec=2)
        return future.result() if future.done() else None

    def safe():
        if not state or time.monotonic() - state['wall'] > 3:
            raise RuntimeError('Missing or stale joint feedback')
        if not math.isfinite(state['q']) or not 0.0005 < state['q'] < 0.034:
            raise RuntimeError(f'Unsafe lift position: {state}')
        endpoints = node.get_subscriptions_info_by_topic(topic)
        if len(endpoints) != 1 or endpoints[0].node_name != 'rb1_elevator_controller':
            raise RuntimeError('Expected exactly one elevator controller subscriber')
        if node.count_publishers(topic) != 1:
            raise RuntimeError('Another lift command publisher is present')

    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            response = request(controllers, ListControllers.Request)
            states = {c.name: c.state for c in response.controller} if response else {}
            if not all(states.get(n) == 'active' for n in (
                    'joint_state_broadcaster', 'rb1_base_controller', 'rb1_elevator_controller')):
                continue
            interfaces = request(hardware, ListHardwareInterfaces.Request)
            claimed = interfaces and any(
                i.name == joint + '/position' and i.is_available and i.is_claimed
                for i in interfaces.command_interfaces)
            try:
                safe()
            except RuntimeError:
                continue
            if claimed and (directory / 'locked').exists():
                break
        else:
            raise RuntimeError('Controller handoff readiness timed out')
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
            safe()
            pub.publish(Float64MultiArray(data=[0.002]))
        # Check the controller's internal target before removing protection.
        for attempt in range(3):
            result = subprocess.run([
                'ros2', 'topic', 'echo', '/controller_manager/introspection_data/full', '--once'],
                capture_output=True, text=True, timeout=10, check=False)
            (directory / f'handoff_{attempt}.log').write_text(result.stdout + result.stderr)
            if result.returncode == 0:
                break
        if result.returncode != 0:
            raise RuntimeError('Internal command snapshot failed')
        values = {item['name']: item['value']
                  for item in next(yaml.safe_load_all(result.stdout))['statistics']}
        command = values['command_interface.' + joint + '/position']
        position = values['state_interface.' + joint + '/position']
        if not math.isfinite(command) or abs(command - 0.002) >= 1e-9:
            raise RuntimeError('Controller did not accept the 2 mm holding target')
        if not math.isfinite(position) or abs(position - 0.002) >= 0.0002:
            raise RuntimeError('Internal position is not near the protected start')
        rclpy.spin_once(node, timeout_sec=0.1)
        safe()
        (directory / 'release').touch()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.05)
            safe()
            if (directory / 'released').exists():
                contents = (directory / 'released').read_text()
                if not contents:
                    continue
                released_at = float(contents)
                if state['sim'] > released_at + 2 and abs(state['q'] - 0.002) < 0.0002:
                    (directory / 'ready').write_text(str(state))
                    print(f'RB1_ELEVATOR_READY position={state["q"]} evidence={directory}', flush=True)
                    return
        raise RuntimeError('Release confirmation or post-release holding failed')
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
