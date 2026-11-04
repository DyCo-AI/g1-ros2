from __future__ import annotations

import math
import threading
import time
import warnings
from pathlib import Path
from typing import Iterable

import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu, PointCloud2
from sensor_msgs_py import point_cloud2
from std_msgs.msg import String
from unitree_go.msg import Go2FrontVideoData
from unitree_hg.msg import HandState, IMUState, LowState

try:
    import rerun as rr
    import rerun.blueprint as rrb
    from rerun.urdf import UrdfJoint, UrdfTree
except ImportError:  # pragma: no cover - exercised on systems without rerun-sdk
    rr = None
    rrb = None
    UrdfJoint = None
    UrdfTree = None

try:
    import gi

    gi.require_version("Gst", "1.0")
    from gi.repository import Gst
except ImportError:  # pragma: no cover - exercised on systems without GStreamer Python
    Gst = None


G1_29DOF_MOTOR_JOINT_NAMES = (
    "left_hip_pitch_joint",
    "left_hip_roll_joint",
    "left_hip_yaw_joint",
    "left_knee_joint",
    "left_ankle_pitch_joint",
    "left_ankle_roll_joint",
    "right_hip_pitch_joint",
    "right_hip_roll_joint",
    "right_hip_yaw_joint",
    "right_knee_joint",
    "right_ankle_pitch_joint",
    "right_ankle_roll_joint",
    "waist_yaw_joint",
    "waist_roll_joint",
    "waist_pitch_joint",
    "left_shoulder_pitch_joint",
    "left_shoulder_roll_joint",
    "left_shoulder_yaw_joint",
    "left_elbow_joint",
    "left_wrist_roll_joint",
    "left_wrist_pitch_joint",
    "left_wrist_yaw_joint",
    "right_shoulder_pitch_joint",
    "right_shoulder_roll_joint",
    "right_shoulder_yaw_joint",
    "right_elbow_joint",
    "right_wrist_roll_joint",
    "right_wrist_pitch_joint",
    "right_wrist_yaw_joint",
)


G1_HAND_JOINT_NAMES = {
    "left": (
        "left_hand_thumb_0_joint",
        "left_hand_thumb_1_joint",
        "left_hand_thumb_2_joint",
        "left_hand_middle_0_joint",
        "left_hand_middle_1_joint",
        "left_hand_index_0_joint",
        "left_hand_index_1_joint",
    ),
    "right": (
        "right_hand_thumb_0_joint",
        "right_hand_thumb_1_joint",
        "right_hand_thumb_2_joint",
        "right_hand_middle_0_joint",
        "right_hand_middle_1_joint",
        "right_hand_index_0_joint",
        "right_hand_index_1_joint",
    ),
}


G1_DEBUG_LINK_MARKERS = {
    "left_thumb_tip": "g1left_hand_thumb_2_link",
    "left_index_tip": "g1left_hand_index_1_link",
    "right_thumb_tip": "g1right_hand_thumb_2_link",
    "right_index_tip": "g1right_hand_index_1_link",
}


DEFAULT_G1_29DOF_HAND_URDF = (
    "third_party/unitree_ros/robots/g1_description/g1_29dof_with_hand_rev_1_0.urdf"
)
DEFAULT_ENABLE_FRONT_VIDEO_TOPIC = False
DEFAULT_ENABLE_STOCK_H264_CAMERA = True


def stock_h264_pipeline(address: str, port: int, interface: str) -> str:
    """Build the passive host-side Unitree multicast receiver pipeline."""
    return (
        f"udpsrc address={address} port={port} multicast-iface={interface} "
        "! application/x-rtp,media=video,encoding-name=H264 "
        "! rtph264depay "
        "! queue max-size-buffers=1 leaky=downstream "
        "! h264parse "
        "! queue max-size-buffers=1 leaky=downstream "
        "! avdec_h264 "
        "! videoconvert "
        "! video/x-raw,format=RGB "
        "! appsink name=sink emit-signals=false max-buffers=1 drop=true sync=false"
    )


class G1RerunBridge(Node):
    """Read-only ROS 2 bridge from Unitree G1 topics into Rerun."""

    def __init__(self) -> None:
        super().__init__("g1_rerun_bridge")

        self.declare_parameter("lowstate_topic", "/lf/lowstate")
        self.declare_parameter("lidar_topic", "/utlidar/cloud_livox_mid360")
        self.declare_parameter("lidar_imu_topic", "/utlidar/imu_livox_mid360")
        self.declare_parameter("secondary_imu_topic", "/lf/secondary_imu")
        self.declare_parameter("camera_topic", "/frontvideostream")
        self.declare_parameter("service_state_topic", "/servicestate")
        self.declare_parameter("left_hand_topic", "/lf/dex3/left/state")
        self.declare_parameter("right_hand_topic", "/lf/dex3/right/state")
        self.declare_parameter("max_lidar_points", 50000)
        self.declare_parameter("spawn_viewer", True)
        self.declare_parameter("enable_motors", False)
        self.declare_parameter("enable_lowstate_imu", True)
        self.declare_parameter("enable_lidar", True)
        self.declare_parameter("enable_lidar_imu", True)
        self.declare_parameter("enable_secondary_imu", True)
        self.declare_parameter("enable_hands", True)
        self.declare_parameter("enable_hand_taxels", True)
        self.declare_parameter("enable_taxel_images", True)
        self.declare_parameter("taxel_baseline_samples", 50)
        self.declare_parameter("taxel_smoothing_alpha", 0.35)
        self.declare_parameter("taxel_pressure_valid_min", 100000.0)
        self.declare_parameter("taxel_pressure_invalid_value", 30000.0)
        self.declare_parameter("taxel_pressure_invalid_tolerance", 1000.0)
        self.declare_parameter("taxel_pressure_scale", 10000.0)
        self.declare_parameter("taxel_pressure_deadband", 0.5)
        self.declare_parameter("taxel_pressure_max", 10.0)
        self.declare_parameter("taxel_pressure_gamma", 0.65)
        self.declare_parameter("taxel_visual_spread", 0.45)
        self.declare_parameter("taxel_visual_pad_fill", 0.35)
        self.declare_parameter("enable_hand_imu", False)
        self.declare_parameter("enable_service_state", False)
        self.declare_parameter("enable_camera", DEFAULT_ENABLE_FRONT_VIDEO_TOPIC)
        self.declare_parameter("enable_camera_packet_preview", True)
        self.declare_parameter(
            "enable_gstreamer_camera", DEFAULT_ENABLE_STOCK_H264_CAMERA
        )
        self.declare_parameter("gstreamer_camera_address", "230.1.1.1")
        self.declare_parameter("gstreamer_camera_port", 1720)
        self.declare_parameter("gstreamer_camera_interface", "enp0s31f6")
        self.declare_parameter("gstreamer_camera_fps_limit", 15.0)
        self.declare_parameter("camera_resolution", "720p")
        self.declare_parameter("robot_model_path", DEFAULT_G1_29DOF_HAND_URDF)
        self.declare_parameter("enable_robot_model_animation", True)
        self.declare_parameter("enable_robot_model_debug_markers", False)
        self.declare_parameter("enable_live_value_debug", False)
        self.declare_parameter("enable_default_blueprint", True)

        if rr is None:
            raise RuntimeError(
                "rerun-sdk is not installed. Install it with: "
                "python3 -m pip install rerun-sdk"
            )

        spawn_viewer = bool(self.get_parameter("spawn_viewer").value)
        rr.init("unitree_g1_diagnostics", spawn=spawn_viewer)
        self._send_default_blueprint()
        self._robot_joints_by_motor_id: list[UrdfJoint | None] = []
        self._hand_joints_by_side: dict[str, list[UrdfJoint | None]] = {}
        self._log_robot_model()

        self._lowstate_count = 0
        self._lidar_count = 0
        self._lidar_imu_count = 0
        self._camera_count = 0
        self._gstreamer_camera_count = 0
        self._gstreamer_camera_stop = threading.Event()
        self._gstreamer_camera_thread: threading.Thread | None = None
        self._time_lock = threading.Lock()
        self._hand_counts = {"left": 0, "right": 0}
        self._taxel_baseline_buffers: dict[str, list[np.ndarray]] = {"left": [], "right": []}
        self._taxel_baselines: dict[str, np.ndarray] = {}
        self._taxel_smoothed: dict[str, np.ndarray] = {}
        self._rerun_frame = 0

        if (
            self._enabled("enable_motors")
            or self._enabled("enable_lowstate_imu")
            or self._robot_joints_by_motor_id
        ):
            self.create_subscription(
                LowState,
                self.get_parameter("lowstate_topic").value,
                self._on_lowstate,
                10,
            )
        if self._enabled("enable_lidar"):
            rr.log(
                "g1/lidar/mid360/points",
                rr.CoordinateFrame("g1mid360_link"),
                static=True,
            )
            self.create_subscription(
                PointCloud2,
                self.get_parameter("lidar_topic").value,
                self._on_lidar,
                10,
            )
        if self._enabled("enable_lidar_imu"):
            self.create_subscription(
                Imu,
                self.get_parameter("lidar_imu_topic").value,
                self._on_lidar_imu,
                50,
            )
        if self._enabled("enable_secondary_imu"):
            self.create_subscription(
                IMUState,
                self.get_parameter("secondary_imu_topic").value,
                self._on_secondary_imu,
                50,
            )
        if self._enabled("enable_service_state"):
            self.create_subscription(
                String,
                self.get_parameter("service_state_topic").value,
                self._on_service_state,
                10,
            )
        if self._enabled("enable_hands"):
            self.create_subscription(
                HandState,
                self.get_parameter("left_hand_topic").value,
                lambda msg: self._on_hand_state("left", msg),
                10,
            )
            self.create_subscription(
                HandState,
                self.get_parameter("right_hand_topic").value,
                lambda msg: self._on_hand_state("right", msg),
                10,
            )
        if self._enabled("enable_camera"):
            self.create_subscription(
                Go2FrontVideoData,
                self.get_parameter("camera_topic").value,
                self._on_front_video,
                10,
            )
        if self._enabled("enable_gstreamer_camera"):
            self._start_gstreamer_camera()

        self.get_logger().info("Rerun bridge started in read-only mode.")

    def _enabled(self, parameter_name: str) -> bool:
        return bool(self.get_parameter(parameter_name).value)

    def _send_default_blueprint(self) -> None:
        if not self._enabled("enable_default_blueprint") or rrb is None:
            return

        blueprint = rrb.Blueprint(
            rrb.Vertical(
                rrb.Horizontal(
                    rrb.Spatial3DView(
                        name="Scene",
                        origin="/",
                        spatial_information=rrb.SpatialInformation(target_frame="g1pelvis"),
                        eye_controls=rrb.archetypes.EyeControls3D(
                            position=[-2.4, -3.0, 1.4],
                            look_target=[0.0, 0.0, 0.8],
                        ),
                    ),
                    rrb.Grid(
                        rrb.Spatial2DView(
                            name="Front Camera",
                            origin="g1/camera/front/image",
                            contents="$origin",
                        ),
                        rrb.Spatial2DView(
                            name="Left Hand Tactile Raw",
                            origin="g1/hands/left/taxel_image/pressure",
                            contents="$origin",
                        ),
                        rrb.Spatial2DView(
                            name="Right Hand Tactile Raw",
                            origin="g1/hands/right/taxel_image/pressure",
                            contents="$origin",
                        ),
                        grid_columns=1,
                        name="Sensors",
                    ),
                    column_shares=[3, 1],
                ),
                rrb.Horizontal(
                    rrb.TimeSeriesView(
                        name="Body IMU Accel",
                        origin="g1/imus/body/accel_m_s2",
                        contents="$origin/**",
                    ),
                    rrb.TimeSeriesView(
                        name="Body IMU Gyro",
                        origin="g1/imus/body/gyro_rad_s",
                        contents="$origin/**",
                    ),
                    rrb.TimeSeriesView(
                        name="Body IMU RPY",
                        origin="g1/imus/body/rpy_rad",
                        contents="$origin/**",
                    ),
                    column_shares=[1, 1, 1],
                    name="Diagnostics",
                ),
                row_shares=[3, 1],
            ),
            collapse_panels=False,
        )
        rr.send_blueprint(blueprint)

    def _log_robot_model(self) -> None:
        model_path_value = str(self.get_parameter("robot_model_path").value).strip()
        if not model_path_value:
            rr.log("g1/robot_model/status", rr.TextDocument("No robot_model_path configured."))
            return

        model_path = self._resolve_model_path(model_path_value)
        if not model_path.exists():
            self.get_logger().warning(f"Robot model path does not exist: {model_path}")
            rr.log(
                "g1/robot_model/status",
                rr.TextDocument(f"Robot model path does not exist: {model_path}"),
            )
            return

        if model_path.suffix.lower() in {".urdf", ".xacro"}:
            self._log_urdf_model(model_path)
            return

        rr.log("g1/robot_model/asset", rr.Asset3D(path=model_path), static=True)
        self.get_logger().info(f"Logged robot model asset: {model_path}")

    def _resolve_model_path(self, model_path_value: str) -> Path:
        model_path = Path(model_path_value).expanduser()
        if model_path.is_absolute():
            return model_path

        candidates = [Path.cwd() / model_path]
        for parent in Path(__file__).resolve().parents:
            candidates.append(parent / model_path)
            candidates.append(parent.parent / model_path)

        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    def _log_urdf_model(self, model_path: Path) -> None:
        if UrdfTree is None:
            self.get_logger().warning("Rerun URDF support is not available.")
            return

        try:
            tree = UrdfTree.from_file_path(
                model_path,
                entity_path_prefix="g1/robot_model",
                frame_prefix="g1",
            )
            tree.log_urdf_to_recording()
        except Exception as exc:  # pragma: no cover - depends on external assets
            self.get_logger().warning(f"Failed to load URDF model {model_path}: {exc}")
            rr.log("g1/robot_model/status", rr.TextDocument(f"URDF load failed: {exc}"))
            return

        self._robot_joints_by_motor_id = self._map_g1_29dof_joints(tree)
        self._hand_joints_by_side = self._map_g1_hand_joints(tree)
        self._log_robot_model_debug_markers()
        rr.log("g1/robot_model/status", rr.TextDocument(f"Loaded URDF: {model_path}"))
        self.get_logger().info(
            f"Logged URDF robot model: {model_path} "
            f"body_joints={sum(j is not None for j in self._robot_joints_by_motor_id)} "
            f"hand_joints={sum(j is not None for joints in self._hand_joints_by_side.values() for j in joints)}"
        )

    def _map_g1_29dof_joints(self, tree: UrdfTree) -> list[UrdfJoint | None]:
        joints_by_motor_id = [tree.get_joint_by_name(name) for name in G1_29DOF_MOTOR_JOINT_NAMES]
        missing = [
            name
            for name, joint in zip(G1_29DOF_MOTOR_JOINT_NAMES, joints_by_motor_id)
            if joint is None
        ]
        if missing:
            self.get_logger().warning(
                "URDF is missing expected G1 29-DOF joints: " + ", ".join(missing)
            )
        return joints_by_motor_id

    def _map_g1_hand_joints(self, tree: UrdfTree) -> dict[str, list[UrdfJoint | None]]:
        joints_by_side = {
            side: [tree.get_joint_by_name(name) for name in joint_names]
            for side, joint_names in G1_HAND_JOINT_NAMES.items()
        }
        for side, joints in joints_by_side.items():
            missing = [
                name
                for name, joint in zip(G1_HAND_JOINT_NAMES[side], joints)
                if joint is None
            ]
            if missing:
                self.get_logger().info(
                    f"URDF does not include {side} hand joints: " + ", ".join(missing)
                )
        return joints_by_side

    def _log_robot_model_debug_markers(self) -> None:
        if not self._enabled("enable_robot_model_debug_markers"):
            return

        colors = {
            "left_thumb_tip": [255, 80, 80],
            "left_index_tip": [255, 180, 80],
            "right_thumb_tip": [80, 160, 255],
            "right_index_tip": [80, 255, 180],
        }
        for name, frame in G1_DEBUG_LINK_MARKERS.items():
            rr.log(
                f"g1/debug_frames/{name}",
                rr.CoordinateFrame(frame),
                rr.Points3D([[0.0, 0.0, 0.0]], radii=0.015, colors=[colors[name]]),
                static=True,
            )

    def _set_rerun_time(self) -> None:
        with self._time_lock:
            self._rerun_frame += 1
            rr.set_time("robot_frame", sequence=self._rerun_frame)

    def _on_lowstate(self, msg: LowState) -> None:
        self._lowstate_count += 1
        self._set_rerun_time()

        rr.log("g1/lowstate/mode_pr", rr.Scalars(int(msg.mode_pr)))
        rr.log("g1/lowstate/mode_machine", rr.Scalars(int(msg.mode_machine)))
        if self._enabled("enable_lowstate_imu"):
            rr.log("g1/lowstate/imu/temperature_c", rr.Scalars(int(msg.imu_state.temperature)))
            self._log_vector("g1/lowstate/imu/quaternion", msg.imu_state.quaternion)
            self._log_vector("g1/lowstate/imu/gyro_rad_s", msg.imu_state.gyroscope)
            self._log_vector("g1/lowstate/imu/accel_m_s2", msg.imu_state.accelerometer)
            self._log_vector("g1/lowstate/imu/rpy_rad", msg.imu_state.rpy)
            self._log_unitree_imu_state("g1/imus/body", msg.imu_state)

        if self._enabled("enable_motors"):
            for motor_id, motor in enumerate(msg.motor_state):
                base = f"g1/motors/m{motor_id:02d}"
                rr.log(f"{base}/q_rad", rr.Scalars(float(motor.q)))
                rr.log(f"{base}/dq_rad_s", rr.Scalars(float(motor.dq)))
                rr.log(f"{base}/tau_est_nm", rr.Scalars(float(motor.tau_est)))
                rr.log(f"{base}/voltage_v", rr.Scalars(float(motor.vol)))
                rr.log(f"{base}/temperature_0_c", rr.Scalars(int(motor.temperature[0])))
                rr.log(f"{base}/temperature_1_c", rr.Scalars(int(motor.temperature[1])))
                rr.log(f"{base}/state_word", rr.Scalars(int(motor.motorstate)))

        if self._enabled("enable_robot_model_animation"):
            self._log_robot_model_joint_transforms(msg)

        if self._lowstate_count % 100 == 1:
            self.get_logger().info(
                f"Logged lowstate tick={msg.tick} motors={len(msg.motor_state)}"
            )

    def _log_robot_model_joint_transforms(self, msg: LowState) -> None:
        if not self._robot_joints_by_motor_id:
            return

        for motor_id, joint in enumerate(self._robot_joints_by_motor_id):
            if joint is None or motor_id >= len(msg.motor_state):
                continue
            try:
                transform = joint.compute_transform(float(msg.motor_state[motor_id].q), clamp=False)
            except Exception as exc:
                if self._lowstate_count % 100 == 1:
                    self.get_logger().warning(
                        f"Failed to compute transform for {joint.name}: {exc}"
                    )
                continue
            rr.log("g1/robot_model/transforms", transform)

    def _on_lidar(self, msg: PointCloud2) -> None:
        self._lidar_count += 1
        self._set_rerun_time()

        points = self._pointcloud_xyz(msg)
        if points.size == 0:
            return

        max_points = int(self.get_parameter("max_lidar_points").value)
        if len(points) > max_points:
            step = int(math.ceil(len(points) / max_points))
            points = points[::step]

        rr.log("g1/lidar/mid360/points", rr.Points3D(points))

        if self._lidar_count % 30 == 1:
            self.get_logger().info(f"Logged LiDAR cloud points={len(points)}")

    def _on_lidar_imu(self, msg: Imu) -> None:
        self._lidar_imu_count += 1
        self._set_rerun_time()

        rr.log("g1/lidar/imu/orientation/x", rr.Scalars(float(msg.orientation.x)))
        rr.log("g1/lidar/imu/orientation/y", rr.Scalars(float(msg.orientation.y)))
        rr.log("g1/lidar/imu/orientation/z", rr.Scalars(float(msg.orientation.z)))
        rr.log("g1/lidar/imu/orientation/w", rr.Scalars(float(msg.orientation.w)))
        rr.log("g1/lidar/imu/angular_velocity/x", rr.Scalars(float(msg.angular_velocity.x)))
        rr.log("g1/lidar/imu/angular_velocity/y", rr.Scalars(float(msg.angular_velocity.y)))
        rr.log("g1/lidar/imu/angular_velocity/z", rr.Scalars(float(msg.angular_velocity.z)))
        rr.log("g1/lidar/imu/linear_acceleration/x", rr.Scalars(float(msg.linear_acceleration.x)))
        rr.log("g1/lidar/imu/linear_acceleration/y", rr.Scalars(float(msg.linear_acceleration.y)))
        rr.log("g1/lidar/imu/linear_acceleration/z", rr.Scalars(float(msg.linear_acceleration.z)))
        rr.log("g1/imus/lidar/orientation/x", rr.Scalars(float(msg.orientation.x)))
        rr.log("g1/imus/lidar/orientation/y", rr.Scalars(float(msg.orientation.y)))
        rr.log("g1/imus/lidar/orientation/z", rr.Scalars(float(msg.orientation.z)))
        rr.log("g1/imus/lidar/orientation/w", rr.Scalars(float(msg.orientation.w)))
        rr.log("g1/imus/lidar/angular_velocity/x", rr.Scalars(float(msg.angular_velocity.x)))
        rr.log("g1/imus/lidar/angular_velocity/y", rr.Scalars(float(msg.angular_velocity.y)))
        rr.log("g1/imus/lidar/angular_velocity/z", rr.Scalars(float(msg.angular_velocity.z)))
        rr.log("g1/imus/lidar/linear_acceleration/x", rr.Scalars(float(msg.linear_acceleration.x)))
        rr.log("g1/imus/lidar/linear_acceleration/y", rr.Scalars(float(msg.linear_acceleration.y)))
        rr.log("g1/imus/lidar/linear_acceleration/z", rr.Scalars(float(msg.linear_acceleration.z)))

    def _on_secondary_imu(self, msg: IMUState) -> None:
        self._set_rerun_time()
        self._log_unitree_imu_state("g1/imus/secondary", msg)

    def _on_front_video(self, msg: Go2FrontVideoData) -> None:
        self._camera_count += 1
        self._set_rerun_time()

        resolution = str(self.get_parameter("camera_resolution").value).lower()
        payload = self._front_video_payload(msg, resolution)
        if not payload:
            rr.log(
                "g1/status/camera",
                rr.TextDocument(f"No front camera payload for resolution={resolution}"),
            )
            return

        media_type = self._encoded_image_media_type(payload)
        if media_type is None:
            status = (
                f"Unsupported front camera encoding: resolution={resolution} "
                f"bytes={len(payload)} magic={payload[:16].hex()}"
            )
            rr.log(
                "g1/status/camera",
                rr.TextDocument(status),
            )
            rr.log("g1/camera/front/encoded_bytes", rr.Scalars(len(payload)))
            if self._enabled("enable_camera_packet_preview"):
                self._log_camera_packet_preview(payload)
            if self._camera_count % 30 == 1:
                self.get_logger().warning(status)
            return

        rr.log(
            "g1/camera/front/image",
            rr.EncodedImage(contents=payload, media_type=media_type),
        )
        if self._camera_count % 30 == 1:
            self.get_logger().info(
                f"Logged front camera frame resolution={resolution} bytes={len(payload)}"
            )

    def _log_camera_packet_preview(self, payload: bytes) -> None:
        if not payload:
            return

        width = 32
        values = np.frombuffer(payload, dtype=np.uint8)
        height = int(math.ceil(len(values) / width))
        padded = np.zeros(width * height, dtype=np.uint8)
        padded[: len(values)] = values
        gray = padded.reshape((height, width))
        preview = np.repeat(gray[:, :, np.newaxis], 3, axis=2)
        rr.log("g1/camera/front/image", rr.Image(preview))

    def _start_gstreamer_camera(self) -> None:
        self.get_logger().info(
            "Starting passive Unitree H264 receiver; no onboard camera process "
            "or device ownership is modified."
        )
        if Gst is None:
            message = (
                "GStreamer Python bindings are not available. Install: "
                "sudo apt install python3-gi gir1.2-gstreamer-1.0"
            )
            self.get_logger().warning(message)
            rr.log("g1/status/camera", rr.TextDocument(message))
            return

        self._gstreamer_camera_thread = threading.Thread(
            target=self._run_gstreamer_camera,
            name="g1_gstreamer_camera",
            daemon=True,
        )
        self._gstreamer_camera_thread.start()

    def _run_gstreamer_camera(self) -> None:
        Gst.init(None)
        address = str(self.get_parameter("gstreamer_camera_address").value)
        port = int(self.get_parameter("gstreamer_camera_port").value)
        interface = str(self.get_parameter("gstreamer_camera_interface").value)
        fps_limit = float(self.get_parameter("gstreamer_camera_fps_limit").value)
        frame_period = 1.0 / fps_limit if fps_limit > 0.0 else 0.0
        last_logged = 0.0

        pipeline_text = stock_h264_pipeline(address, port, interface)

        try:
            pipeline = Gst.parse_launch(pipeline_text)
        except Exception as exc:
            message = f"Failed to create GStreamer camera pipeline: {exc}"
            self.get_logger().warning(message)
            rr.log("g1/status/camera", rr.TextDocument(message))
            return

        sink = pipeline.get_by_name("sink")
        if sink is None:
            message = "GStreamer camera pipeline did not create appsink."
            self.get_logger().warning(message)
            rr.log("g1/status/camera", rr.TextDocument(message))
            return

        pipeline.set_state(Gst.State.PLAYING)
        rr.log(
            "g1/status/camera",
            rr.TextDocument(f"GStreamer camera started: {address}:{port} iface={interface}"),
        )
        self.get_logger().info(f"GStreamer camera started: {address}:{port} iface={interface}")

        try:
            while not self._gstreamer_camera_stop.is_set():
                sample = sink.emit("try-pull-sample", 250_000_000)
                if sample is None:
                    continue

                now = time.monotonic()
                if frame_period > 0.0 and now - last_logged < frame_period:
                    continue
                last_logged = now

                frame = self._gstreamer_sample_to_rgb(sample)
                if frame is None:
                    continue

                self._gstreamer_camera_count += 1
                self._set_rerun_time()
                rr.log("g1/camera/front/image", rr.Image(frame))
                if self._gstreamer_camera_count % 60 == 1:
                    height, width = frame.shape[:2]
                    self.get_logger().info(
                        f"Logged GStreamer camera frame {width}x{height}"
                    )
        finally:
            pipeline.set_state(Gst.State.NULL)

    def _gstreamer_sample_to_rgb(self, sample) -> np.ndarray | None:
        buffer = sample.get_buffer()
        caps = sample.get_caps()
        if buffer is None or caps is None or caps.get_size() == 0:
            return None

        structure = caps.get_structure(0)
        width = structure.get_value("width")
        height = structure.get_value("height")
        success, map_info = buffer.map(Gst.MapFlags.READ)
        if not success:
            return None

        try:
            frame = np.frombuffer(map_info.data, dtype=np.uint8)
            expected_size = int(width) * int(height) * 3
            if frame.size < expected_size:
                return None
            return frame[:expected_size].reshape((int(height), int(width), 3)).copy()
        finally:
            buffer.unmap(map_info)

    def destroy_node(self) -> bool:
        self._gstreamer_camera_stop.set()
        if self._gstreamer_camera_thread is not None:
            self._gstreamer_camera_thread.join(timeout=2.0)
        return super().destroy_node()

    def _front_video_payload(self, msg: Go2FrontVideoData, resolution: str) -> bytes:
        if resolution == "180p":
            return bytes(msg.video180p)
        if resolution == "360p":
            return bytes(msg.video360p)
        return bytes(msg.video720p)

    def _encoded_image_media_type(self, payload: bytes) -> str | None:
        if payload.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if payload.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        return None

    def _on_service_state(self, msg: String) -> None:
        rr.log("g1/health/service_state", rr.TextDocument(msg.data or ""))
        debug_mode = 1.0 if not msg.data.strip() or "inactive" in msg.data.lower() else 0.0
        rr.log("g1/health/debug_mode_likely", rr.Scalars(debug_mode))

    def _on_hand_state(self, side: str, msg: HandState) -> None:
        self._hand_counts[side] += 1
        self._set_rerun_time()

        self._log_motor_array(f"g1/hands/{side}/motors", msg.motor_state)
        rr.log(f"g1/hands/{side}/power_v", rr.Scalars(float(msg.power_v)))
        rr.log(f"g1/hands/{side}/power_a", rr.Scalars(float(msg.power_a)))
        rr.log(f"g1/hands/{side}/system_v", rr.Scalars(float(msg.system_v)))
        rr.log(f"g1/hands/{side}/device_v", rr.Scalars(float(msg.device_v)))
        if self._enabled("enable_hand_taxels"):
            self._log_hand_taxels(side, msg)
        if self._enabled("enable_hand_imu"):
            self._log_unitree_imu_state(f"g1/imus/hands/{side}", msg.imu_state)
        if self._enabled("enable_robot_model_animation"):
            self._log_hand_joint_transforms(side, msg)
        if self._enabled("enable_live_value_debug"):
            self._log_live_hand_value_debug(side, msg)
        if self._hand_counts[side] % 50 == 1:
            positions = ", ".join(f"{float(motor.q):.3f}" for motor in msg.motor_state[:7])
            self.get_logger().info(f"{side} hand q[0:7]=[{positions}]")

    def _log_hand_taxels(self, side: str, msg: HandState) -> None:
        pressure_rows = []
        for sensor_id, sensor in enumerate(msg.press_sensor_state):
            pressures = [float(value) for value in sensor.pressure]
            temperatures = [float(value) for value in sensor.temperature]
            root = f"g1/hands/{side}/taxels/s{sensor_id:02d}"
            pressure_rows.append(pressures)

            rr.log(f"{root}/pressure_grid", rr.BarChart(pressures))
            rr.log(f"{root}/temperature_grid", rr.BarChart(temperatures))
            rr.log(f"{root}/lost", rr.Scalars(int(sensor.lost)))

            for taxel_id, pressure in enumerate(pressures):
                rr.log(f"{root}/pressure/t{taxel_id:02d}", rr.Scalars(pressure))
            for taxel_id, temperature in enumerate(temperatures):
                rr.log(f"{root}/temperature/t{taxel_id:02d}", rr.Scalars(temperature))

        if self._enabled("enable_taxel_images"):
            self._log_taxel_heatmap_image(side, pressure_rows)

    def _log_taxel_heatmap_image(self, side: str, pressure_rows: list[list[float]]) -> None:
        if not pressure_rows:
            return

        pressures = self._processed_taxel_pressures(side, pressure_rows)
        image = self._render_dex3_hand_taxel_image(side, pressures)
        rr.log(f"g1/hands/{side}/taxel_image/pressure", rr.Image(image))

    def _processed_taxel_pressures(self, side: str, pressure_rows: list[list[float]]) -> np.ndarray:
        raw = self._pressure_rows_to_matrix(pressure_rows)
        if raw.size == 0:
            return raw

        valid = self._valid_taxel_mask(raw)
        baseline = self._taxel_baselines.get(side)
        target_samples = int(self.get_parameter("taxel_baseline_samples").value)
        if baseline is None and target_samples > 0:
            buffer = self._taxel_baseline_buffers[side]
            buffer.append(np.where(valid, raw, np.nan))
            if len(buffer) >= target_samples:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", category=RuntimeWarning)
                    baseline = np.nanmedian(np.stack(buffer, axis=0), axis=0)
                baseline = np.nan_to_num(
                    baseline,
                    nan=float(self.get_parameter("taxel_pressure_valid_min").value),
                )
                self._taxel_baselines[side] = baseline
                self.get_logger().info(
                    f"{side} Dex3 tactile raw baseline ready samples={len(buffer)}"
                )
                rr.log(
                    f"g1/hands/{side}/taxel_status",
                    rr.TextDocument(f"baseline ready samples={len(buffer)}"),
                )
            else:
                rr.log(
                    f"g1/hands/{side}/taxel_status",
                    rr.TextDocument(f"collecting baseline {len(buffer)}/{target_samples}"),
                )
                return np.zeros_like(raw, dtype=np.float32)

        if baseline is None:
            baseline = np.zeros_like(raw, dtype=np.float32)

        scale = float(self.get_parameter("taxel_pressure_scale").value)
        if scale <= 0.0:
            scale = 10000.0

        delta = np.where(valid, np.maximum(raw - baseline, 0.0) / scale, 0.0)
        alpha = float(self.get_parameter("taxel_smoothing_alpha").value)
        alpha = float(np.clip(alpha, 0.0, 1.0))
        previous = self._taxel_smoothed.get(side)
        if previous is not None and previous.shape == delta.shape:
            delta = alpha * delta + (1.0 - alpha) * previous
        self._taxel_smoothed[side] = delta

        deadband = float(self.get_parameter("taxel_pressure_deadband").value)
        if deadband > 0.0:
            delta = np.where(delta > deadband, delta - deadband, 0.0)
        return delta

    def _pressure_rows_to_matrix(self, pressure_rows: list[list[float]]) -> np.ndarray:
        if not pressure_rows:
            return np.empty((0, 12), dtype=np.float32)
        rows = []
        for row in pressure_rows:
            row_values = list(row)
            rows.append((row_values + [0.0] * 12)[:12])
        return np.asarray(rows, dtype=np.float32)

    def _valid_taxel_mask(self, raw: np.ndarray) -> np.ndarray:
        valid_min = float(self.get_parameter("taxel_pressure_valid_min").value)
        invalid_value = float(self.get_parameter("taxel_pressure_invalid_value").value)
        invalid_tolerance = float(self.get_parameter("taxel_pressure_invalid_tolerance").value)
        return (
            np.isfinite(raw)
            & (raw >= valid_min)
            & (np.abs(raw - invalid_value) > invalid_tolerance)
        )

    def _render_dex3_hand_taxel_image(self, side: str, pressure_values: np.ndarray) -> np.ndarray:
        image = np.full((260, 360, 3), [18, 20, 24], dtype=np.uint8)
        outline = np.array([72, 78, 88], dtype=np.uint8)
        palm_fill = np.array([34, 38, 45], dtype=np.uint8)

        palm_x, palm_y, palm_w, palm_h = 132, 166, 96, 72
        image[palm_y : palm_y + palm_h, palm_x : palm_x + palm_w] = palm_fill
        image[palm_y : palm_y + 2, palm_x : palm_x + palm_w] = outline
        image[palm_y + palm_h - 2 : palm_y + palm_h, palm_x : palm_x + palm_w] = outline
        image[palm_y : palm_y + palm_h, palm_x : palm_x + 2] = outline
        image[palm_y : palm_y + palm_h, palm_x + palm_w - 2 : palm_x + palm_w] = outline

        for sensor_id, x, y, width, height in self._dex3_pressure_pad_layout(side):
            if sensor_id >= len(pressure_values):
                continue
            self._paste_taxel_pad(
                image,
                pressure_values[sensor_id],
                x=x,
                y=y,
                pad_size=(width, height),
            )

        return image

    def _dex3_pressure_pad_layout(self, side: str) -> list[tuple[int, int, int, int, int]]:
        left_layout = [
            (5, 104, 22, 52, 58),
            (4, 104, 86, 52, 58),
            (3, 204, 22, 52, 58),
            (2, 204, 86, 52, 58),
            (6, 84, 164, 58, 34),
            (7, 150, 164, 58, 34),
            (8, 216, 164, 58, 34),
            (0, 292, 154, 46, 34),
            (1, 292, 198, 46, 34),
        ]
        if side != "right":
            return left_layout

        canvas_width = 360
        mirrored = []
        for sensor_id, x, y, width, height in left_layout:
            mirrored.append((sensor_id, canvas_width - x - width, y, width, height))
        return mirrored

    def _paste_taxel_pad(
        self,
        image: np.ndarray,
        pressures: Iterable[float],
        x: int,
        y: int,
        pad_size: tuple[int, int],
    ) -> None:
        pad = self._render_taxel_pad(pressures, pad_size)
        height, width = pad.shape[:2]
        image[y : y + height, x : x + width] = pad

    def _render_taxel_pad(self, pressures: Iterable[float], pad_size: tuple[int, int]) -> np.ndarray:
        width, height = pad_size
        pad = np.full((height, width, 3), [42, 46, 54], dtype=np.uint8)
        pressure_list = list(pressures)
        values = np.asarray((pressure_list + [0.0] * 12)[:12], dtype=np.float32).reshape((3, 4))
        normalized = self._normalize_pressures(values)
        display_values = self._display_taxel_pressures(normalized)
        colors = self._pressure_colormap_uint8(display_values)

        pad_level = float(np.max(normalized)) if normalized.size else 0.0
        fill_ratio = float(self.get_parameter("taxel_visual_pad_fill").value)
        fill_ratio = float(np.clip(fill_ratio, 0.0, 1.0))
        if pad_level > 0.0 and fill_ratio > 0.0:
            fill_color = self._pressure_colormap_uint8(
                np.asarray([[pad_level * fill_ratio]], dtype=np.float32)
            )[0, 0]
            pad[:, :] = fill_color

        cell_w = width // 4
        cell_h = height // 3
        for row in range(3):
            for column in range(4):
                x0 = column * cell_w
                y0 = row * cell_h
                x1 = width if column == 3 else (column + 1) * cell_w
                y1 = height if row == 2 else (row + 1) * cell_h
                pad[y0:y1, x0:x1] = colors[row, column]

        grid_color = np.asarray([18, 20, 24], dtype=np.uint8)
        for column in range(1, 4):
            x = column * cell_w
            pad[:, max(0, x - 1) : min(width, x + 1)] = grid_color
        for row in range(1, 3):
            y = row * cell_h
            pad[max(0, y - 1) : min(height, y + 1), :] = grid_color
        return pad

    def _display_taxel_pressures(self, normalized: np.ndarray) -> np.ndarray:
        spread = float(self.get_parameter("taxel_visual_spread").value)
        spread = float(np.clip(spread, 0.0, 1.0))
        if spread <= 0.0:
            return normalized

        padded = np.pad(normalized, 1, mode="edge")
        neighbor_max = np.zeros_like(normalized)
        for row_offset in range(3):
            for column_offset in range(3):
                if row_offset == 1 and column_offset == 1:
                    continue
                neighbor_max = np.maximum(
                    neighbor_max,
                    padded[
                        row_offset : row_offset + normalized.shape[0],
                        column_offset : column_offset + normalized.shape[1],
                    ],
                )
        return np.maximum(normalized, neighbor_max * spread)

    def _normalize_pressures(self, pressures: np.ndarray) -> np.ndarray:
        values = np.asarray(pressures, dtype=np.float32)
        configured_max = float(self.get_parameter("taxel_pressure_max").value)
        pressure_max = configured_max if configured_max > 0.0 else float(np.max(values))
        if pressure_max <= 0.0:
            pressure_max = 1.0
        normalized = np.clip(values / pressure_max, 0.0, 1.0)
        gamma = float(self.get_parameter("taxel_pressure_gamma").value)
        if gamma > 0.0:
            normalized = np.power(normalized, gamma)
        return normalized

    def _pressure_colormap_uint8(self, normalized: np.ndarray) -> np.ndarray:
        values = np.asarray(normalized, dtype=np.float32)
        stops = np.asarray(
            [
                [0, 0, 95],
                [0, 80, 255],
                [0, 220, 255],
                [80, 255, 80],
                [255, 230, 0],
                [255, 70, 0],
                [180, 0, 0],
            ],
            dtype=np.float32,
        )
        scaled = np.clip(values, 0.0, 1.0) * (len(stops) - 1)
        lower = np.floor(scaled).astype(np.int32)
        upper = np.clip(lower + 1, 0, len(stops) - 1)
        blend = (scaled - lower)[..., np.newaxis]
        colors = stops[lower] * (1.0 - blend) + stops[upper] * blend
        colors = np.where(values[..., np.newaxis] <= 0.0, [22, 26, 34], colors)
        return np.clip(colors, 0.0, 255.0).astype(np.uint8)

    def _log_live_hand_value_debug(self, side: str, msg: HandState) -> None:
        points = []
        labels = []
        x_offset = -0.25 if side == "left" else 0.25
        for motor_id, motor in enumerate(msg.motor_state[:7]):
            points.append([x_offset + 0.04 * motor_id, 0.08 * float(motor.q), 1.35])
            labels.append(f"{side[0]}{motor_id}")
        color = [255, 110, 80] if side == "left" else [80, 170, 255]
        rr.log(
            f"g1/debug_live/{side}_hand_q_points",
            rr.CoordinateFrame("g1pelvis"),
            rr.Points3D(points, radii=0.018, colors=[color], labels=labels),
        )

    def _log_hand_joint_transforms(self, side: str, msg: HandState) -> None:
        joints = self._hand_joints_by_side.get(side, [])
        if not joints:
            return

        for motor_id, joint in enumerate(joints):
            if joint is None or motor_id >= len(msg.motor_state):
                continue
            try:
                transform = joint.compute_transform(float(msg.motor_state[motor_id].q), clamp=False)
            except Exception as exc:
                self.get_logger().warning(f"Failed to compute transform for {joint.name}: {exc}")
                continue
            rr.log("g1/robot_model/transforms", transform)

    def _log_motor_array(self, root: str, motors: Iterable) -> None:
        for motor_id, motor in enumerate(motors):
            base = f"{root}/m{motor_id:02d}"
            rr.log(f"{base}/q_rad", rr.Scalars(float(motor.q)))
            rr.log(f"{base}/dq_rad_s", rr.Scalars(float(motor.dq)))
            rr.log(f"{base}/tau_est_nm", rr.Scalars(float(motor.tau_est)))
            rr.log(f"{base}/state_word", rr.Scalars(int(motor.motorstate)))

    def _log_vector(self, root: str, values: Iterable[float]) -> None:
        for index, value in enumerate(values):
            rr.log(f"{root}/{index}", rr.Scalars(float(value)))

    def _log_unitree_imu_state(self, root: str, imu_state: IMUState) -> None:
        rr.log(f"{root}/temperature_c", rr.Scalars(int(imu_state.temperature)))
        self._log_named_values(
            f"{root}/quaternion",
            ("x", "y", "z", "w"),
            imu_state.quaternion,
        )
        self._log_named_values(
            f"{root}/gyro_rad_s",
            ("roll_rate", "pitch_rate", "yaw_rate"),
            imu_state.gyroscope,
        )
        self._log_named_values(
            f"{root}/accel_m_s2",
            ("ax", "ay", "az"),
            imu_state.accelerometer,
        )
        self._log_named_values(
            f"{root}/rpy_rad",
            ("roll", "pitch", "yaw"),
            imu_state.rpy,
        )

    def _log_named_values(
        self,
        root: str,
        names: Iterable[str],
        values: Iterable[float],
    ) -> None:
        for name, value in zip(names, values):
            rr.log(f"{root}/{name}", rr.Scalars(float(value)))

    def _pointcloud_xyz(self, msg: PointCloud2) -> np.ndarray:
        points = []
        for point in point_cloud2.read_points(
            msg,
            field_names=("x", "y", "z"),
            skip_nans=True,
        ):
            points.append((float(point[0]), float(point[1]), float(point[2])))

        if not points:
            return np.empty((0, 3), dtype=np.float32)

        return np.asarray(points, dtype=np.float32)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = G1RerunBridge()
        rclpy.spin(node)
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
