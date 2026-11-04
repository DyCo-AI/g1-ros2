# Ubuntu 22.04 Host Installation

This is the clean-host installation procedure for `g1-ros2`. Complete it once
on the Ubuntu development PC before following the robot bring-up runbook.

## Tested Baseline

The current project has been developed and tested on:

| Item | Tested configuration |
| --- | --- |
| Host OS | Ubuntu 22.04 LTS (Jammy) |
| Host architecture | x86_64 |
| ROS | ROS 2 Humble desktop |
| ROS middleware | CycloneDDS |
| Python | Python 3.10 using `venv` or Conda |
| Robot interface | `enp0s31f6` |
| Host robot-LAN address | `192.168.123.222/24` |
| Robot | Unitree G1, 29 body DOF, Dex3 hands |

Ubuntu 20.04/Foxy is used on the onboard Jetson, but it is not the supported
host environment for this repository. Do not source Foxy or Noetic on the
Ubuntu 22.04 host. The host can use either the documented Python virtual
environment or the Python 3.10 Conda environment below.

## 1. Verify the Host

```bash
lsb_release -ds
uname -m
```

Expected:

```text
Ubuntu 22.04...
x86_64
```

If the host uses another Ubuntu or ROS release, use a separate machine,
container, or branch until that configuration has been validated.

## 2. Install ROS 2 Humble

Install ROS 2 Humble Desktop using the official ROS instructions:

- [ROS 2 Humble Ubuntu installation](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html)

Return here after `ros-humble-desktop` is installed. Verify the installation in
a new terminal:

```bash
source /opt/ros/humble/setup.bash
echo "$ROS_DISTRO"
which ros2
```

Expected:

```text
humble
/opt/ros/humble/bin/ros2
```

## 3. Install Host Dependencies

```bash
sudo apt update
sudo apt install \
  git \
  python3-colcon-common-extensions \
  python3-opencv \
  python3-pip \
  python3-rosdep \
  python3-venv \
  python3-vcstool \
  python3-gi \
  python3-gst-1.0 \
  gir1.2-gstreamer-1.0 \
  build-essential \
  cmake \
  libeigen3-dev \
  libyaml-cpp-dev \
  ros-humble-rmw-cyclonedds-cpp \
  ros-humble-rosidl-generator-dds-idl \
  gstreamer1.0-tools \
  gstreamer1.0-libav \
  gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad
```

Initialize `rosdep` once per host:

```bash
sudo rosdep init
rosdep update
```

If `rosdep init` reports that its sources list already exists, do not remove
it; continue with `rosdep update`.

## 4. Clone `g1-ros2`

```bash
cd ~
git clone https://github.com/DyCo-AI/g1-ros2.git
cd g1-ros2
```

Import the pinned Unitree source dependencies:

```bash
vcs import < dependencies.repos
```

This creates:

```text
src/unitree_ros2
third_party/unitree_ros
third_party/unitree_model
third_party/unitree_sdk2
```

Verify the pinned checkouts:

```bash
vcs status --hide-empty
```

Do not run `git pull` independently inside these dependency directories during
a normal installation. Update `dependencies.repos` through a reviewed change
when the lab intentionally changes an upstream revision.

## 5. Choose a Python Environment

Choose exactly one option for a checkout. The standard `venv` path has the
fewest interactions with ROS and is the default for new lab users. Conda is
also supported for local development when it uses Python 3.10 and exposes the
Ubuntu Python packages required by ROS, OpenCV, and GStreamer.

### Option A: `venv` (Recommended)

Use a virtual environment that can still see Ubuntu's ROS Python packages:

```bash
cd ~/g1-ros2
/usr/bin/python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r src/g1_rerun_bridge/requirements.txt
```

Verify the visualization dependencies:

```bash
python3 -c "import numpy, rerun; print('numpy', numpy.__version__); print('rerun', rerun.__version__)"
```

### Option B: Conda

Create a dedicated Python 3.10 environment. Do not install ROS itself from
Conda; ROS 2 Humble remains the Ubuntu installation under `/opt/ros/humble`.

```bash
cd ~/g1-ros2
conda create --name g1-ros2 python=3.10 pip -y
conda activate g1-ros2

printf '%s\n' '/usr/lib/python3/dist-packages' \
  > "$CONDA_PREFIX/lib/python3.10/site-packages/ubuntu-system.pth"

python3 -m pip install --upgrade pip
python3 -m pip install -r src/g1_rerun_bridge/requirements.txt
```

The `.pth` file gives the environment access to Ubuntu's `colcon`, OpenCV,
PyGObject, and GStreamer bindings. Sourcing ROS later adds the ROS 2 Python
packages from `/opt/ros/humble`.

Verify the complete Conda environment:

```bash
source /opt/ros/humble/setup.bash
python3 -c "import sys, colcon_core, cv2, gi, numpy, rclpy, rerun; assert sys.version_info[:2] == (3, 10); print('Conda environment: PASS')"
```

If a Conda environment uses another Python minor version, recreate it with
Python 3.10. Humble's Ubuntu binaries are built for Python 3.10.

### Switching Options

Do not activate `.venv` and Conda at the same time. To switch an existing
checkout, deactivate the old environment, remove the generated workspace
outputs, activate the new environment, and rebuild:

```bash
deactivate 2>/dev/null || true
conda deactivate 2>/dev/null || true
rm -rf build install log
```

The removal is limited to generated colcon output. It does not remove source
code, configuration, or datasets.

## 6. Build Unitree ROS 2 Messages

Unitree recommends Ubuntu 22.04 with ROS 2 Humble and CycloneDDS for this
setup. The source revision used by the lab is pinned in `dependencies.repos`.

```bash
cd ~/g1-ros2
# Activate exactly one:
source .venv/bin/activate
# conda activate g1-ros2

source /opt/ros/humble/setup.bash

rosdep install \
  --from-paths src/unitree_ros2/cyclonedds_ws/src \
  --ignore-src -r -y

cd src/unitree_ros2/cyclonedds_ws
/usr/bin/python3 -m colcon build --symlink-install \
  --cmake-args -DPython3_EXECUTABLE=/usr/bin/python3
source install/setup.bash
cd ../../..
```

Verify the G1 interfaces:

```bash
ros2 interface show unitree_hg/msg/LowState
ros2 interface show unitree_hg/msg/HandState
```

Both commands must print message fields before continuing.

## 7. Build the Lab Diagnostics Packages

```bash
cd ~/g1-ros2
# Activate exactly one:
source .venv/bin/activate
# conda activate g1-ros2

source /opt/ros/humble/setup.bash
source src/unitree_ros2/cyclonedds_ws/install/setup.bash

python3 -m colcon build --symlink-install \
  --packages-select g1_rerun_bridge g1_rerun_dex

source install/setup.bash
```

Verify the installed entry points:

```bash
ros2 pkg executables g1_rerun_bridge
ros2 pkg executables g1_rerun_dex
```

Expected executables:

```text
g1_rerun_bridge bridge
g1_rerun_dex dex_rerun
```

The motion-capable `g1_teleop` package uses the pinned native Unitree SDK2 tree
imported above. Build it only after the read-only stack works, following the
[teleoperation runbook](../teleop/README.md).

## 8. Configure the Robot Ethernet Profile

Connect the PC to the robot LAN and find the wired interface:

```bash
ip -brief link
nmcli device status
```

The tested host uses `enp0s31f6`. Configure and verify it with the project
script:

```bash
cd ~/g1-ros2
sudo ./scripts/configure_g1_lan.sh \
  enp0s31f6 \
  192.168.123.222/24 \
  192.168.123.161
```

If your interface name differs, pass that interface and update
`config/cyclonedds_g1.xml` to use the same name. The host address must be an
unused address on `192.168.123.0/24`; never assign the robot's `.161` address
to the host.

See the [network runbook](../network/README.md) for persistent NetworkManager
configuration and troubleshooting.

## 9. Source a New Terminal

Run this sequence in every terminal used with the robot:

```bash
cd ~/g1-ros2
# Activate exactly one:
source .venv/bin/activate
# conda activate g1-ros2

source /opt/ros/humble/setup.bash
source src/unitree_ros2/cyclonedds_ws/install/setup.bash
source install/setup.bash

export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI="file://${PWD}/config/cyclonedds_g1.xml"
```

Verify that the terminal is not contaminated by another ROS environment:

```bash
echo "ROS_DISTRO=$ROS_DISTRO"
echo "RMW_IMPLEMENTATION=$RMW_IMPLEMENTATION"
echo "CYCLONEDDS_URI=$CYCLONEDDS_URI"
which python3
```

Expected ROS distribution: `humble`. Python should resolve to either
`~/g1-ros2/.venv/bin/python3` or the `g1-ros2` Conda environment's Python 3.10.

## 10. Installation Pass Criteria

The host installation is complete when all of these pass without the robot:

```bash
ros2 interface show unitree_hg/msg/LowState
ros2 pkg executables g1_rerun_bridge
ros2 pkg executables g1_rerun_dex
python3 -c "import gi; gi.require_version('Gst', '1.0'); from gi.repository import Gst; import rclpy, rerun, numpy, cv2; print('host dependencies: PASS')"
gst-inspect-1.0 h264parse
gst-inspect-1.0 avdec_h264
```

Then connect the supported robot, put it in development mode, and run:

```bash
ping -c 4 192.168.123.161
ros2 topic list
ros2 topic info /lf/lowstate
ros2 topic hz /lf/lowstate
```

Only after these checks pass should the user continue to the
[whole-robot diagnostics bring-up](../bringup/README.md).

## Updating an Existing Checkout

```bash
cd ~/g1-ros2
git pull --ff-only
vcs import < dependencies.repos

# Activate exactly one:
source .venv/bin/activate
# conda activate g1-ros2

source /opt/ros/humble/setup.bash
source src/unitree_ros2/cyclonedds_ws/install/setup.bash

python3 -m pip install -r src/g1_rerun_bridge/requirements.txt
python3 -m colcon build --symlink-install \
  --packages-select g1_rerun_bridge g1_rerun_dex
```

Re-source `install/setup.bash` after rebuilding.

## Common Installation Failures

| Symptom | Resolution |
| --- | --- |
| `rosidl-generator-dds-idl` download returns `404` | Run `sudo apt update`, then retry. Do not use a stale package index. |
| `unitree_hg/msg/LowState is invalid` | Build and source `src/unitree_ros2/cyclonedds_ws/install/setup.bash`. |
| Unitree message generation selects Conda Python | Use the documented `/usr/bin/python3 -m colcon` message build command. |
| Conda cannot import `gi`, `cv2`, or `colcon_core` | Recreate `ubuntu-system.pth` exactly as shown in Option B. |
| Conda reports native-library or symbol errors | Start a clean terminal, activate only `g1-ros2`, then source Humble. Use Option A if the conflict remains. |
| `No module named rerun` | Activate the selected environment and reinstall the requirements file. |
| Ping works but no ROS topics appear | Check CycloneDDS URI, interface name, RMW implementation, and development mode. |
| Camera panel is empty | Verify GStreamer plugins and the multicast interface using the camera runbook. |

## References

- [Official ROS 2 Humble Ubuntu installation](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html)
- [Official Unitree ROS 2 repository](https://github.com/unitreerobotics/unitree_ros2)
- [Unitree G1 developer guide](https://support.unitree.com/home/en/G1_developer/about_G1)
