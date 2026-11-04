# g1-ros

ROS 2 bring-up, diagnostics, bounded teleoperation, and dataset capture tools
for the DyCo AI Lab's Unitree G1 humanoid.

[![ROS 2 Humble](https://img.shields.io/badge/ROS%202-Humble-22314E)](https://docs.ros.org/en/humble/)
[![Platform](https://img.shields.io/badge/platform-Unitree%20G1-2E7D32)](https://support.unitree.com/home/en/G1_developer/about_G1)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-hardware%20validation%20in%20progress-orange)](#project-status)

> [!IMPORTANT]
> This repository includes motion-capable code. Keep the G1 supported on its
> gantry during initial tests, clear the workspace, keep the remote/emergency
> stop available, and run the read-only checks before enabling motion.

![Live G1 URDF, Mid360 LiDAR, front camera, Dex3 tactile state, and IMU diagnostics in Rerun](docs/assets/g1_rerun_overview.png)

## Purpose

`g1-ros` provides a repeatable starting point for new lab users and controller
developers. Its core workflow is:

1. Connect a development PC to the G1 and verify the robot network.
2. Configure ROS 2 Humble and CycloneDDS for Unitree communication.
3. Discover and inspect body, hand, camera, LiDAR, IMU, and health messages.
4. Visualize the live robot and sensors in Rerun.
5. Run small, explicitly enabled Dex3 and upper-body teleoperation tests.
6. Record synchronized robot data and replay it without the robot connected.

The diagnostics path is read-only. Motion tests live in a separate package and
require explicit operator activation.

## Supported Lab Robot

The current profile targets the lab's development-capable G1 configuration:

| Component | Configuration |
| --- | --- |
| Robot | Unitree G1, 29 body DOF |
| Hands | Left and right Dex3-1, 7 motors per hand |
| LiDAR | Livox Mid360 |
| Camera | Intel RealSense D435i plus Unitree H264 RGB stream |
| Onboard computer | NVIDIA Jetson Orin NX |
| Development PC | Ubuntu 22.04, ROS 2 Humble |
| ROS middleware | CycloneDDS |

Do not assume these instructions apply unchanged to a 23-DOF G1, dummy hands,
another firmware version, or another lab network.

## What You Can Inspect

| System | Primary source | Current support |
| --- | --- | --- |
| Body joints and primary IMU | `/lf/lowstate` | Live ROS and animated URDF |
| Secondary IMU | `/lf/secondary_imu` | Live ROS and Rerun plots |
| Mid360 cloud and IMU | `/utlidar/cloud_livox_mid360`, `/utlidar/imu_livox_mid360` | Live ROS and 3D Rerun view |
| Dex3 state and tactile arrays | `/lf/dex3/left/state`, `/lf/dex3/right/state` | Live ROS, URDF, tactile diagnostics |
| Front RGB camera | Unitree H264 multicast | Live GStreamer decode in Rerun |
| RealSense depth | Onboard D435i | Isolated Foxy driver probe works; integration pending |
| Battery, board, alarms, stop state | Unitree low-frequency topics | Topic inventory exists; readiness summary pending |

## Interfaces

### Whole-Robot Diagnostics

The main Rerun interface combines the live G1 model, Mid360 cloud, front RGB
camera, body IMU, and both Dex3 hands:

```bash
ros2 run g1_rerun_bridge bridge
```

### Dex3 Diagnostics

The focused hand interface groups raw tactile packets by physical pad and
plots their values over time:

```bash
ros2 run g1_rerun_dex dex_rerun
```

![Dex3 tactile layouts, grouped raw taxels, and time-series diagnostics](docs/dex3/assets/g1_rerun_dex.png)

### Bounded Dex3 Motion Test

The first teleoperation milestone uses native Unitree SDK2. It starts read-only
unless `--enable-motion` is supplied:

```bash
# Read-only feedback check
ros2 run g1_teleop dex3_smoke enp0s31f6 --side right

# Motion-capable mode: only after completing the safety checklist
ros2 run g1_teleop dex3_smoke enp0s31f6 \
  --side right \
  --enable-motion
```

See the [teleoperation runbook](docs/teleop/README.md) before using the second
command.

## Quick Start

### 1. Clone the Repository and Upstream Dependencies

```bash
git clone https://github.com/DyCo-AI/g1-ros.git
cd g1-ros

sudo apt update
sudo apt install python3-vcstool
vcs import < dependencies.repos
```

The dependency manifest pins the Unitree ROS 2 messages and robot-description
repositories used by this workspace. Generated `build/`, `install/`, and `log/`
directories are not committed.

### 2. Install the Host Dependencies

The supported host baseline is Ubuntu 22.04 with ROS 2 Humble:

```bash
sudo apt update
sudo apt install \
  ros-humble-desktop \
  ros-humble-rmw-cyclonedds-cpp \
  ros-humble-rosidl-generator-dds-idl \
  python3-colcon-common-extensions \
  python3-rosdep \
  python3-pip \
  gstreamer1.0-tools \
  gstreamer1.0-libav \
  gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad

python3 -m pip install -r src/g1_rerun_bridge/requirements.txt
```

### 3. Build Unitree Messages and Lab Packages

```bash
source /opt/ros/humble/setup.bash

cd src/unitree_ros2/cyclonedds_ws
colcon build --symlink-install
source install/setup.bash
cd ../../..

colcon build --symlink-install \
  --packages-select g1_rerun_bridge g1_rerun_dex
source install/setup.bash
```

The motion-capable `g1_teleop` package has a separate SDK2 build procedure in
the [teleoperation documentation](docs/teleop/README.md).

### 4. Prepare the Robot and Network

1. Support the G1 on the gantry.
2. Power it on and wait for startup.
3. Use `L2 + R2`, then `L2 + A`, then `L2 + B` to enter the current lab
   development pose.
4. Confirm the development-mode LED is green.
5. Connect the development PC by Ethernet.
6. Confirm the PC Ethernet address is `192.168.123.222/24`.
7. Verify the robot every session:

```bash
ping -c 4 192.168.123.161
```

Do not continue unless the ping check passes. See the complete
[network runbook](docs/network/README.md) for first-time configuration and
Jetson access.

### 5. Source DDS and Check Messages

From the repository root:

```bash
source /opt/ros/humble/setup.bash
source src/unitree_ros2/cyclonedds_ws/install/setup.bash
source install/setup.bash

export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI="file://${PWD}/config/cyclonedds_g1.xml"

ros2 topic list
ros2 topic info /lf/lowstate
ros2 topic hz /lf/lowstate
ros2 topic echo --once /lf/lowstate --field mode_machine
```

Then follow the [whole-robot bring-up](docs/bringup/README.md) to validate each
sensor and start Rerun.

## Saving Data

Raw ROS topics can already be captured with `ros2 bag record`. For example:

```bash
mkdir -p datasets
ros2 bag record -o datasets/g1_smoke \
  /lf/lowstate \
  /lf/secondary_imu \
  /lf/dex3/left/state \
  /lf/dex3/right/state \
  /utlidar/cloud_livox_mid360 \
  /utlidar/imu_livox_mid360
```

The planned V1 recording command will add:

- MCAP storage and named recording profiles.
- Rerun `.rrd` capture.
- Camera/depth synchronization.
- Hardware, firmware, calibration, and clock metadata.
- A 10-second automated smoke test and offline replay validation.

Until that workflow is complete, treat manually recorded bags as development
data rather than accepted lab datasets.

## Repository Layout

```text
config/                     CycloneDDS and robot profiles
docs/                       Lab runbooks and subsystem documentation
scripts/                    Network, calibration, and diagnostic utilities
src/g1_rerun_bridge/        Whole-robot ROS-to-Rerun diagnostics
src/g1_rerun_dex/           Focused Dex3 tactile diagnostics
src/g1_teleop/              Explicitly enabled bounded motion tests
third_party/                Local, ignored binary dependencies
dependencies.repos          Pinned upstream source dependencies
```

## Documentation

| Start here | Purpose |
| --- | --- |
| [Lab wiki](docs/README.md) | Documentation index and conventions |
| [Whole-robot bring-up](docs/bringup/README.md) | Canonical startup and diagnostics procedure |
| [Network and development mode](docs/network/README.md) | Ethernet, static IP, ping, DDS, and Jetson SSH |
| [Hardware configuration](docs/hardware/README.md) | Robot variant, sensors, hip clamp, and active DOFs |
| [Rerun diagnostics](docs/rerun/README.md) | Whole-robot interface and troubleshooting |
| [Dex3 diagnostics](docs/dex3/README.md) | Tactile layout, calibration, and focused viewer |
| [Camera](docs/camera/README.md) | Unitree RGB and RealSense investigation |
| [LiDAR](docs/lidar/README.md) | Mid360 topics, rates, and frame checks |
| [IMUs](docs/imus/README.md) | Body, secondary, and Mid360 IMUs |
| [Basic teleoperation](docs/teleop/README.md) | Bounded hand test and safety procedure |
| [V1/V2 pilot roadmap](docs/pilots/README.md) | Acceptance criteria and remaining work |

## Project Status

| Milestone | Status |
| --- | --- |
| Robot LAN, ping, ROS 2 messages, and DDS discovery | Working |
| Live URDF, RGB camera, Mid360, IMUs, and Dex3 in Rerun | Working baseline |
| Focused Dex3 tactile diagnostics and calibration tools | Working baseline |
| Native SDK2 bounded hand test | Implemented and offline-tested; hardware acceptance pending |
| Automated subsystem readiness report | Planned |
| Native RealSense RGB/depth integration | In progress |
| 10-second MCAP + RRD recording and offline replay | Planned |
| Deadman-controlled basic teleoperation | Planned after deterministic motion tests |
| Locomotion | Out of scope for the initial pilot |

The detailed release gates are maintained in the
[pilot roadmap](docs/pilots/README.md). A feature is not considered validated
only because it compiles or appears in Rerun; hardware pass criteria and saved
evidence must also be completed.

## External References

- [Unitree G1 developer guide](https://support.unitree.com/home/en/G1_developer/about_G1)
- [Unitree G1 quick development guide](https://support.unitree.com/home/en/G1_developer/quick_development)
- [Unitree ROS 2](https://github.com/unitreerobotics/unitree_ros2)
- [Unitree SDK2](https://github.com/unitreerobotics/unitree_sdk2)
- [Unitree G1 robot description](https://github.com/unitreerobotics/unitree_ros/tree/master/robots/g1_description)
- [RoboStore G1 startup guide](https://robostore.com/blogs/news/unitree-g1-startup-guide-essential-steps-for-setup-calibration-and-control)

The Unitree documentation is authoritative for robot operation and SDK
behavior. Third-party startup material is linked as supplementary onboarding
context and must not override Unitree safety or firmware-specific guidance.

## License

Lab-authored code and documentation are released under the [MIT License](LICENSE).
Upstream Unitree repositories, robot assets, SDK libraries, and other external
dependencies retain their own licenses.
