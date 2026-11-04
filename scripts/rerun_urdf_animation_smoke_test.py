#!/usr/bin/env python3
from __future__ import annotations

import math
import time
from pathlib import Path

import rerun as rr
from rerun.urdf import UrdfTree


URDF_PATH = Path(
    "third_party/unitree_ros/robots/g1_description/g1_29dof_with_hand_rev_1_0.urdf"
)


def main() -> None:
    if not URDF_PATH.exists():
        raise FileNotFoundError(f"Missing URDF: {URDF_PATH}")

    rr.init("g1_urdf_animation_smoke_test", spawn=True)

    tree = UrdfTree.from_file_path(
        URDF_PATH,
        entity_path_prefix="g1/robot_model",
        frame_prefix="g1",
    )
    tree.log_urdf_to_recording()

    right_index = tree.get_joint_by_name("right_hand_index_1_joint")
    right_thumb = tree.get_joint_by_name("right_hand_thumb_2_joint")
    if right_index is None or right_thumb is None:
        raise RuntimeError("Expected G1 hand joints are missing from the URDF")

    rr.log(
        "g1/debug_live/direct_point",
        rr.Points3D([[0.0, 0.0, 1.2]], radii=0.03, colors=[[255, 0, 0]]),
    )

    frame = 0
    while True:
        frame += 1
        angle = 0.8 + 0.7 * math.sin(frame * 0.06)
        direct_y = 0.4 * math.sin(frame * 0.06)

        rr.set_time("robot_frame", sequence=frame)
        rr.log("g1/robot_model/transforms", right_index.compute_transform(angle))
        rr.log("g1/robot_model/transforms", right_thumb.compute_transform(-angle))
        rr.log(
            "g1/debug_live/direct_point",
            rr.Points3D([[0.0, direct_y, 1.2]], radii=0.03, colors=[[255, 0, 0]]),
        )

        if frame % 30 == 0:
            print(f"frame={frame} angle={angle:.3f} direct_y={direct_y:.3f}", flush=True)
        time.sleep(1.0 / 30.0)


if __name__ == "__main__":
    main()
