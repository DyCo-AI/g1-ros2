# Unitree G1 Lab Diagnostics Wiki

This folder is the lab-facing documentation area for Unitree G1 diagnostics.
Keep the root `README.md` focused on project setup and the current main path.
Put subsystem-specific runbooks, calibration notes, and troubleshooting here.

## Suggested Wiki Layout

| Folder | Purpose |
| --- | --- |
| `docs/pilots/` | Versioned V1 diagnostics and V2 teleoperation acceptance-test plans. |
| `docs/bringup/` | Canonical whole-robot startup and read-only diagnostics procedure. |
| `docs/hardware/` | Physical robot configuration, hip clamp state, active DOFs, and controller compatibility. |
| `docs/network/` | Development mode, LAN setup, static IP, ping checks, DDS/network troubleshooting. |
| `docs/dex3/` | Dex3 hand tactile diagnostics, raw taxel layout, calibration, smoke tests, hand command checks. |
| `docs/lidar/` | Mid360 topics, point cloud checks, Rerun/RViz visualization, frame alignment, camera/LiDAR fusion notes. |
| `docs/camera/` | GStreamer camera stream, ROS video topics, recording/replay, frame rate and latency checks. |
| `docs/imus/` | Body, secondary, Mid360, and optional Dex3 hand IMU streams, validation, and recording. |
| `docs/rerun/` | Rerun layouts, recordings, `.rrd` replay, screenshot conventions, GUI troubleshooting. |
| `docs/teleop/` | Explicitly enabled Dex3 and upper-body motion tests, safety gates, and controller operation. |

## Documentation Pattern

For each subsystem, prefer this structure:

1. What hardware/topic is being tested.
2. How to run the diagnostic.
3. What a passing result looks like.
4. What data is raw vs calibrated.
5. Common failures and fixes.
6. Links to source documentation and lab recordings.

## Current Subsystem Docs

- [V1 diagnostics and V2 teleoperation pilot roadmap](pilots/README.md)
- [Whole-robot diagnostics bring-up](bringup/README.md)
- [Hardware configuration and hip clamp](hardware/README.md)
- [Network and development mode](network/README.md)
- [Rerun diagnostics](rerun/README.md)
- [Dex3 tactile diagnostics](dex3/README.md)
- [IMU diagnostics](imus/README.md)
- [Basic teleoperation and Dex3 motion smoke test](teleop/README.md)

## Sensor and Telemetry Inventory

The main raw or near-raw streams worth recording are:

| Category | Primary source | What it contains | Documentation |
| --- | --- | --- | --- |
| Camera | H264 multicast and `/frontvideostream` | Front RGB video | [`camera/`](camera/README.md) |
| LiDAR | `/utlidar/cloud_livox_mid360` | Raw Mid360 `PointCloud2` | [`lidar/`](lidar/README.md) |
| IMUs | Body, secondary, Mid360, optional Dex3 IMUs | Acceleration, angular velocity, orientation, temperature | [`imus/`](imus/README.md) |
| Dex3 tactile | `/lf/dex3/left/state`, `/lf/dex3/right/state` | Raw taxels, hand joints, temperature, hand IMUs | [`dex3/`](dex3/README.md) |
| Body motors | `/lf/lowstate` | Joint position/velocity, estimated torque, voltage, temperature, state | TODO: robot-state runbook |
| Battery/board health | `/lf/bmsstate`, `/lf/agvbmsstate`, `/lf/mainboardstate` | Power and controller health telemetry | TODO: health runbook |
| Operator input | `/wirelesscontroller` | Remote/controller state | TODO: controls runbook |
| Safety state | `/lf/emergency_stop`, `/lf/battery_alarm`, `/servicestate` | Stop, alarm, and service state | TODO: health runbook |

Processed outputs such as SLAM odometry/maps and collision or safety point
clouds can also be recorded, but keep them separate from the raw sensor profile
so the source data needed to reproduce them remains clear.
