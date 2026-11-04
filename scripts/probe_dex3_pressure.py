#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time

import rclpy
from rclpy.node import Node
from unitree_hg.msg import HandState


class Dex3PressureProbe(Node):
    def __init__(self, threshold: float, print_hz: float) -> None:
        super().__init__("dex3_pressure_probe")
        self.threshold = threshold
        self.print_period = 1.0 / print_hz if print_hz > 0.0 else 0.5
        self.last_print = 0.0
        self.latest: dict[str, HandState] = {}
        self.create_subscription(
            HandState,
            "/lf/dex3/left/state",
            lambda msg: self._on_hand("left", msg),
            10,
        )
        self.create_subscription(
            HandState,
            "/lf/dex3/right/state",
            lambda msg: self._on_hand("right", msg),
            10,
        )

    def _on_hand(self, side: str, msg: HandState) -> None:
        self.latest[side] = msg
        now = time.monotonic()
        if now - self.last_print < self.print_period:
            return
        self.last_print = now
        self._print_summary()

    def _print_summary(self) -> None:
        print("-" * 80)
        for side in ("left", "right"):
            msg = self.latest.get(side)
            if msg is None:
                print(f"{side}: no message yet")
                continue

            print(f"{side}: sensors={len(msg.press_sensor_state)}")
            for sensor_id, sensor in enumerate(msg.press_sensor_state):
                values = [float(value) for value in sensor.pressure]
                sensor_max = max(values) if values else 0.0
                sensor_sum = sum(values)
                active_taxels = [
                    f"t{taxel_id:02d}={value:.3f}"
                    for taxel_id, value in enumerate(values)
                    if abs(value) >= self.threshold
                ]
                active = " ".join(active_taxels[:12]) if active_taxels else "-"
                print(
                    f"  s{sensor_id:02d}: max={sensor_max:.3f} "
                    f"sum={sensor_sum:.3f} lost={int(sensor.lost)} active={active}"
                )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print live Dex3 pressure sensor summaries for mapping pads."
    )
    parser.add_argument("--threshold", type=float, default=0.02)
    parser.add_argument("--print-hz", type=float, default=2.0)
    args = parser.parse_args()

    rclpy.init()
    node = Dex3PressureProbe(threshold=args.threshold, print_hz=args.print_hz)
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
