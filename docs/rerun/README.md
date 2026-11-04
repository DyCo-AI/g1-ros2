# Rerun Diagnostics

This page documents the Rerun interface produced by `g1_rerun_bridge`. For the
complete robot startup sequence, begin with the [whole-robot bring-up
runbook](../bringup/README.md).

## Run the Default Layout

From a terminal sourced according to the
[bring-up runbook](../bringup/README.md):

```bash
ros2 run g1_rerun_bridge bridge
```

The node starts a Rerun viewer and sends the default blueprint automatically.
The bridge is read-only and does not publish command topics.

## Default Views

| View | Data |
| --- | --- |
| `Scene` | Live G1 URDF, joint transforms, and Mid360 point cloud |
| `Front Camera` | Decoded Unitree H264 multicast video |
| `Left Hand Tactile Raw` | Left Dex3 tactile colormap |
| `Right Hand Tactile Raw` | Right Dex3 tactile colormap |
| `Body IMU Accel` | Body `ax`, `ay`, `az` |
| `Body IMU Gyro` | Body roll, pitch, and yaw angular rates |
| `Body IMU RPY` | Processed body roll, pitch, and yaw orientation |

The entity tree contains additional logged streams even when they do not have
a dedicated panel. Use the eye icon to show or hide entities and create
additional time-series views as needed.

## Main Stream Toggles

| Parameter | Default | Stream |
| --- | --- | --- |
| `enable_robot_model_animation` | `true` | Live body and hand URDF joints |
| `enable_lidar` | `true` | Mid360 point cloud |
| `enable_lowstate_imu` | `true` | Body IMU |
| `enable_lidar_imu` | `true` | Mid360 IMU |
| `enable_secondary_imu` | `true` | Secondary Unitree IMU |
| `enable_hands` | `true` | Dex3 state |
| `enable_hand_taxels` | `true` | Dex3 raw taxels |
| `enable_hand_imu` | `false` | Left/right Dex3 IMUs |
| `enable_gstreamer_camera` | `true` | H264 multicast camera |
| `enable_motors` | `false` | Body motor telemetry |
| `enable_service_state` | `false` | Service/debug state |

Example:

```bash
ros2 run g1_rerun_bridge bridge --ros-args \
  -p enable_motors:=true \
  -p enable_hand_imu:=true
```

## Important Entity Paths

| Rerun path | Content |
| --- | --- |
| `g1/robot_model` | G1 URDF geometry and transforms |
| `g1/lidar/mid360/points` | Raw point cloud |
| `g1/camera/front/image` | Decoded camera frames |
| `g1/imus/body` | Body IMU channels |
| `g1/imus/secondary` | Secondary IMU channels |
| `g1/imus/lidar` | Mid360 IMU channels |
| `g1/imus/hands/*` | Optional Dex3 IMU channels |
| `g1/hands/*` | Dex3 joints and tactile data |
| `g1/motors/mXX/*` | Optional body motor telemetry |

## Camera Interface

The camera defaults to multicast interface `enp0s31f6`, address `230.1.1.1`,
and port `1720`. Override the interface when the robot LAN uses another device:

```bash
ros2 run g1_rerun_bridge bridge --ros-args \
  -p gstreamer_camera_interface:=<robot-lan-interface>
```

This is a passive host-side receiver for Unitree's existing stream. It does
not start the isolated onboard RealSense ROS 2 driver or take ownership of the
camera device. Native RealSense RGB/depth remains disabled from default
bring-up; see the [camera safety boundary](../camera/README.md#default-rerun-camera-safety-boundary).

## Expected Behavior

- URDF geometry should appear immediately after launch.
- Joint motion can lag the hardware slightly because the default pose source is
  the low-frequency state stream.
- LiDAR should remain attached to the robot frame without transform errors.
- Camera frames should update continuously rather than showing packet-preview
  imagery.
- Tactile panels should remain mostly dark after untouched baseline collection.

## Troubleshooting

| Symptom | First check |
| --- | --- |
| Viewer does not open | `python3 -c "import rerun; print(rerun.__version__)"` |
| URDF missing | Start from the workspace root and verify the configured URDF path exists. |
| Robot does not animate | Check `/lf/lowstate` and both Dex3 state topics. |
| LiDAR missing | Check `/utlidar/cloud_livox_mid360` rate and target-frame errors. |
| Camera empty | Check the LAN interface and standalone GStreamer stream. |
| IMU panel empty | Check the containing ROS topic and corresponding enable parameter. |
| Tactile panels noisy at rest | Restart with both hands untouched during baseline collection. |

Subsystem runbooks:

- [Camera](../camera/README.md)
- [LiDAR](../lidar/README.md)
- [IMUs](../imus/README.md)
- [Dex3](../dex3/README.md)

## TODO

- [ ] Document `.rrd` recording and replay after the recording smoke test is
  implemented.
- [ ] Add a saved screenshot of the current whole-robot default layout.
- [ ] Validate every default view from a fresh workspace terminal.
