#!/usr/bin/env python3
"""Send a bounded positive-position target; never silently clamp a zero target."""
import argparse
import math
import time
import rclpy
from std_msgs.msg import Float64MultiArray


def main():
    parser = argparse.ArgumentParser(description='Simulation only; wait for RB1_ELEVATOR_READY first.')
    parser.add_argument('position', type=float, help='Metres, from 0.001 to 0.034')
    args = parser.parse_args()
    if not math.isfinite(args.position) or not 0.001 <= args.position <= 0.034:
        parser.error('Use 0.001–0.034 m; zero can stick at the physical lower limit.')
    rclpy.init()
    node = rclpy.create_node('rb1_elevator_command')
    topic = '/rb1_elevator_controller/commands'
    pub = node.create_publisher(Float64MultiArray, topic, 10)
    try:
        deadline = time.monotonic() + 10
        while pub.get_subscription_count() != 1:
            if time.monotonic() > deadline:
                raise RuntimeError('Expected exactly one command subscriber')
            rclpy.spin_once(node, timeout_sec=0.1)
        for _ in range(20):
            if node.count_publishers(topic) != 1:
                raise RuntimeError('Another lift publisher is present; stop it first')
            pub.publish(Float64MultiArray(data=[args.position]))
            rclpy.spin_once(node, timeout_sec=0.1)
        print(f'Sent target {args.position} m; verify /joint_states separately.')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
