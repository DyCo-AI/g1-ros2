# Camera Diagnostics

## Current Status

- [x] Confirm the Intel RealSense D435i is connected to the G1 internal PC at
  `192.168.123.164`.
- [x] Confirm the internal PC runs ROS 2 Foxy and ROS 1 Noetic on Ubuntu 20.04
  ARM64.
- [x] Confirm Unitree's `videohub_pc4` process owns `/dev/video4` and provides
  the existing RGB H264 stream.
- [x] Decode the Unitree H264 multicast stream on the user PC and display it in
  the main Rerun diagnostics view.
- [x] Confirm the internal PC has the Noetic RealSense driver but does not have
  `realsense2_camera` or `ros1_bridge` for Foxy.
- [x] Confirm the QRE/MYBOTSHOP integration packages (`g1_platform`,
  `g1_control`, `g1_interface`, `g1_depth_camera`, `g1_lidar`, `g1_viz`, and
  `g1_webserver`) are not installed on this G1. Treat the QRE guide as a
  reference architecture, not a command-compatible setup guide.
- [x] Confirm compatible Foxy ARM64 RealSense packages are present in the
  cached APT index.
- [x] Download and checksum the pinned Foxy ARM64 RealSense packages on the
  user PC, then transfer them to the G1 auxiliary PC.
- [x] Extract the packages into the isolated
  `/home/unitree/realsense_foxy/root` prefix without modifying APT or
  `/opt/ros/foxy`.
- [x] Verify the isolated RealSense node, message interfaces, and shared
  libraries resolve correctly.
- [x] Complete a bounded depth-only D435i probe at `424x240` and 15 Hz.

## TODO: Native ROS 2 RealSense Access

Do not run `apt --fix-broken install`, remove either time service, stop
`master_service.service`, or overwrite the packages under `/opt/ros`. The
vendor image has both `chrony` and `systemd-timesyncd` installed, which causes
APT dependency resolution to report a conflict even though `dpkg --audit` is
clean.

- [x] Obtain the ARM64 package filenames and dependency metadata for:
  - `ros-foxy-librealsense2`
  - `ros-foxy-realsense2-camera-msgs`
  - `ros-foxy-realsense2-description`
  - `ros-foxy-realsense2-camera`
- [x] Download the matching packages on the internet-connected user PC.
- [x] Transfer the packages to the G1 internal PC with `scp`.
- [x] Extract the packages into an isolated prefix such as
  `/home/unitree/realsense_foxy` using `dpkg-deb -x`; do not install them into
  the robot's system package database.
- [x] Configure an isolated Foxy environment with the extracted prefix in
  `AMENT_PREFIX_PATH`, `LD_LIBRARY_PATH`, and `PATH`.
- [x] Verify `ros2 pkg prefix realsense2_camera` resolves to the isolated
  prefix.
- [x] Launch a bounded low-bandwidth depth-only probe. The probe worked, but
  the front `videohub_pc4` PID changed, indicating camera contention or a
  vendor-process restart that must be understood before routine use.
- [ ] Recharge and safely power up the robot, then resume the read-only
  `master_service`/`videohub_pc4` lifecycle inspection. The previous session
  stopped here because the robot battery discharged.
- [ ] Determine the supported way to suspend only the front `videohub_pc4`
  process for native RealSense capture and restore it afterward.
- [ ] Add a three-mode diagnostics launcher: `stock`, `realsense`, and `off`,
  with optional automatic remote camera management and guaranteed cleanup on
  exit.
- [ ] Verify depth image and camera-info topic names, types, rates, dimensions,
  timestamps, and QoS locally on the G1 internal PC.
- [ ] Verify the standard `sensor_msgs` camera topics are discoverable from the
  ROS 2 Humble user PC over the robot LAN.
- [ ] Add depth images and camera calibration to the main Rerun bridge.
- [ ] Enable and validate point-cloud output only after depth streaming is
  stable.
- [ ] Measure camera latency and check whether the RGB and depth clocks can be
  synchronized sufficiently for RGB-depth or camera-LiDAR fusion.
- [ ] Add RGB/depth recording and offline replay to the RRD and MCAP smoke
  tests.

## Documentation TODO

- [ ] Document the standalone GStreamer RGB test and expected multicast
  address, port, and interface.
- [ ] Document the Unitree `/frontvideostream` message and the difference
  between that ROS topic and the multicast H264 stream.
- [ ] Document Rerun camera checks, expected frame rate, failure modes, and
  recording/replay.
