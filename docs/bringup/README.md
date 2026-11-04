# Whole-Robot Diagnostics Bring-Up

This is the canonical operator procedure for starting the read-only Unitree G1
Rerun diagnostics. Use the subsystem pages for deeper camera, LiDAR, IMU, or
Dex3 testing.

## Prerequisites

- Ubuntu 22.04 with ROS 2 Humble.
- Unitree ROS 2 message workspace built under
  `src/unitree_ros2/cyclonedds_ws`.
- `g1_rerun_bridge` built in this workspace.
- Rerun Python SDK and the camera GStreamer dependencies installed.

Verify the two main software entry points:

```bash
python3 -c "import rerun; print(rerun.__version__)"
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 pkg executables g1_rerun_bridge
```

Expected ROS executable:

```text
g1_rerun_bridge bridge
```

## 1. Prepare the Robot and Enter Development Mode

1. Put the G1 on the gantry and clear the surrounding area.
2. Power on the robot and wait for startup to complete.
3. Press `L2 + R2` on the controller.
4. Press `L2 + A`.
5. Press `L2 + B`.
6. Confirm the development-mode LED is green.

For read-only diagnostics, record whether the hip clamp is installed. Before
running any motion-enabled test or controller, complete the mandatory
[hardware configuration and active-DOF check](../hardware/README.md). The
controller model and command mask must match the physical clamp state.

## 2. Connect and Verify the Robot LAN

Connect the robot LAN cable to the PC. The current lab network is:

| Item | Value |
| --- | --- |
| Robot | `192.168.123.161` |
| PC | `192.168.123.222/24` |
| PC interface | `enp0s31f6` |

The PC address must be a unique address on the robot's `192.168.123.0/24`
subnet. It must not be the robot's `.161` address.

If the NetworkManager profile has not been configured yet, find its name:

```bash
nmcli -f NAME,TYPE,DEVICE connection show --active
```

Then configure it once, replacing `<wired-connection>`:

```bash
sudo nmcli connection modify "<wired-connection>" \
  ipv4.method manual \
  ipv4.addresses 192.168.123.222/24 \
  ipv4.gateway "" \
  ipv4.never-default yes

sudo nmcli connection up "<wired-connection>"
```

Verify the saved setup every session:

```bash
ip -4 address show dev enp0s31f6
ip route get 192.168.123.161
ping -c 4 192.168.123.161
```

The interface must show `192.168.123.222/24`, the route must use
`enp0s31f6`, and ping must report `0% packet loss`.

Do not continue if the ping check fails. The detailed [network
runbook](../network/README.md) covers alternate interfaces and troubleshooting.

## 3. Source the Workspace

Open a terminal at the workspace root:

```bash
cd /home/sriramk/unitree_g1_ws
source /opt/ros/humble/setup.bash
source src/unitree_ros2/cyclonedds_ws/install/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file:///home/sriramk/unitree_g1_ws/config/cyclonedds_g1.xml
source install/setup.bash
```

If the bridge has not been built, build it once and source the workspace again:

```bash
colcon build --symlink-install --packages-select g1_rerun_bridge
source install/setup.bash
```

Confirm DDS discovery before checking every stream:

```bash
ros2 topic list
ros2 topic info /lf/lowstate
```

If robot topics are absent even though ping works, confirm that
`config/cyclonedds_g1.xml` names the current robot Ethernet interface.

## 4. Verify Core Robot Streams

Check that the robot and primary sensors are publishing:

```bash
ros2 topic hz /lf/lowstate
ros2 topic hz /utlidar/cloud_livox_mid360
ros2 topic hz /utlidar/imu_livox_mid360
ros2 topic hz /lf/secondary_imu
ros2 topic hz /lf/dex3/left/state
ros2 topic hz /lf/dex3/right/state
```

Each command runs continuously; press `Ctrl+C` after confirming a stable rate.
The camera uses a separate H264 multicast path, so it is checked in the Rerun
window after launch.

## 5. Start Whole-Robot Rerun

Keep both Dex3 hands untouched during startup so the tactile baseline is clean:

```bash
ros2 run g1_rerun_bridge bridge
```

The bridge is read-only. It subscribes to state and sensor streams and does not
publish robot commands.

The default launch enables:

- Live G1 URDF and joint animation.
- Raw Mid360 LiDAR point cloud.
- Front camera through the Unitree H264 multicast stream.
- Body, secondary, and Mid360 IMU logging.
- Left and right Dex3 state and tactile visualization.

## 6. Confirm the Display

A passing initial bring-up has:

1. The G1 URDF visible in the 3D scene.
2. The robot pose updating from live body and Dex3 joint state.
3. Mid360 points visible and attached to the robot frame.
4. Live front-camera frames.
5. Body IMU acceleration, gyro, and RPY plots updating.
6. Left and right tactile panels dark at rest and responsive to touch.
7. No repeated transform-path or missing-entity errors.

See the [Rerun runbook](../rerun/README.md) for panel details and stream
toggles.

## 7. Stop the Diagnostic

Press `Ctrl+C` in the bridge terminal. The current launch does not send a stop
or motion command to the robot because it never takes command ownership.

## Common Launch Overrides

Use the PC interface connected to the robot if it differs from the default:

```bash
ros2 run g1_rerun_bridge bridge --ros-args \
  -p gstreamer_camera_interface:=enp0s31f6
```

Enable body motor telemetry plots and the optional Dex3 hand IMUs:

```bash
ros2 run g1_rerun_bridge bridge --ros-args \
  -p enable_motors:=true \
  -p enable_hand_imu:=true
```

Disable a problematic stream while debugging another subsystem:

```bash
ros2 run g1_rerun_bridge bridge --ros-args \
  -p enable_gstreamer_camera:=false \
  -p enable_hands:=false
```

## Troubleshooting Order

1. Recheck robot development mode and `ping`.
2. Confirm the CycloneDDS environment and Ethernet interface.
3. Run `ros2 topic info <topic>` and `ros2 topic hz <topic>`.
4. Test the failing subsystem using its dedicated runbook.
5. Restart the bridge with only that subsystem enabled.

## TODO

- [ ] Run this full bring-up procedure from a fresh terminal and record the
  observed topic rates.
- [ ] Add the 10-second MCAP and Rerun replay smoke test.
- [ ] Add an automated read-only readiness summary for all required streams.
