# IMU Diagnostics

This page documents the IMU streams available from the Unitree G1 and how to
check them before recording or visualizing them in Rerun.

## Available IMUs

| IMU | ROS source | Message | Rerun path | Default |
| --- | --- | --- | --- | --- |
| Body IMU | `/lf/lowstate.imu_state` | Embedded `unitree_hg/msg/IMUState` | `g1/imus/body` | Enabled |
| Secondary IMU | `/lf/secondary_imu` | `unitree_hg/msg/IMUState` | `g1/imus/secondary` | Enabled |
| Mid360 IMU | `/utlidar/imu_livox_mid360` | `sensor_msgs/msg/Imu` | `g1/imus/lidar` | Enabled |
| Left Dex3 IMU | `/lf/dex3/left/state.imu_state` | Embedded `unitree_hg/msg/IMUState` | `g1/imus/hands/left` | Disabled |
| Right Dex3 IMU | `/lf/dex3/right/state.imu_state` | Embedded `unitree_hg/msg/IMUState` | `g1/imus/hands/right` | Disabled |

The default diagnostics focus on the body, secondary, and Mid360 IMUs. The
Dex3 hand IMUs can be useful for manipulation experiments but add two more
high-rate streams and are disabled in the bridge by default.

## Data Fields

The Unitree `IMUState` sources provide:

| Field | Meaning | Unit |
| --- | --- | --- |
| `quaternion[4]` | Estimated orientation | Unit quaternion |
| `gyroscope[3]` | Angular velocity about x/y/z | rad/s |
| `accelerometer[3]` | Linear acceleration along x/y/z | m/s^2 |
| `rpy[3]` | Processed roll, pitch, yaw estimate | rad |
| `temperature` | IMU temperature | deg C |

The Mid360 `sensor_msgs/msg/Imu` stream provides orientation, angular
velocity, linear acceleration, and covariance arrays. A covariance filled with
zeros or an orientation covariance beginning with `-1` needs to be interpreted
according to the ROS message convention before treating the orientation as
measured.

These topics do not provide position or linear velocity. Position and velocity
must come from odometry, localization, or state estimation rather than direct
IMU integration in the diagnostics GUI.

## Verify the Streams

Source ROS and the workspace:

```bash
source /opt/ros/humble/setup.bash
source install/setup.bash
```

Check the three default sources:

```bash
ros2 topic info /lf/lowstate
ros2 topic info /lf/secondary_imu
ros2 topic info /utlidar/imu_livox_mid360

ros2 topic hz /lf/lowstate
ros2 topic hz /lf/secondary_imu
ros2 topic hz /utlidar/imu_livox_mid360
```

Print one sample from each source:

```bash
ros2 topic echo --once /lf/lowstate --field imu_state
ros2 topic echo --once /lf/secondary_imu
ros2 topic echo --once /utlidar/imu_livox_mid360
```

Optional Dex3 IMU checks:

```bash
ros2 topic echo --once /lf/dex3/left/state --field imu_state
ros2 topic echo --once /lf/dex3/right/state --field imu_state
```

## Run in Rerun

The body, secondary, and Mid360 IMUs are enabled by default:

```bash
ros2 run g1_rerun_bridge bridge
```

Enable the two Dex3 hand IMUs when needed:

```bash
ros2 run g1_rerun_bridge bridge --ros-args \
  -p enable_hand_imu:=true
```

The default blueprint displays body acceleration, gyroscope, and RPY plots.
The other IMU entities remain available in the Rerun entity tree even when
they do not have a dedicated default panel.

## Passing Checks

An IMU stream passes the initial smoke test when:

1. The expected publisher is present and the topic rate is stable.
2. All reported values are finite.
3. The stationary accelerometer magnitude is reasonably close to gravity.
4. Stationary gyro values remain close to zero without large continuous drift.
5. Orientation changes smoothly when the supported robot or sensor is moved.
6. Timestamps continue advancing and the stream does not freeze.

Do not expect different IMUs to report identical vectors. They are mounted in
different frames and may use different onboard filtering.

## Recording Topics

For raw ROS recording, include the containing messages rather than only the
Rerun-derived scalar paths:

```text
/lf/lowstate
/lf/secondary_imu
/utlidar/imu_livox_mid360
/lf/dex3/left/state       # optional hand IMU plus hand/tactile state
/lf/dex3/right/state      # optional hand IMU plus hand/tactile state
```

## TODO

- [ ] Record and document the observed rate of `/lf/secondary_imu`.
- [ ] Verify the physical mounting frame for the secondary IMU.
- [ ] Verify Mid360 orientation/covariance validity on the current firmware.
- [ ] Compare stationary noise and drift across body, secondary, and Mid360
  IMUs.
- [ ] Decide whether Dex3 hand IMUs belong in the default recording profile.
