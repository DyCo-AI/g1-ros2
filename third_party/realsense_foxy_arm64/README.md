# RealSense ROS 2 Foxy ARM64 Package Bundle

This directory holds the pinned Ubuntu 20.04 ARM64 packages used to test the
Intel RealSense D435i on the G1 auxiliary Jetson without modifying its APT
database or `/opt/ros/foxy` installation.

Downloaded `.deb` files belong in `debs/` and are intentionally excluded from
version control. Verify every checksum before transferring or extracting a
package.

| Package | Version | SHA256 |
| --- | --- | --- |
| `ros-foxy-librealsense2` | `2.51.1-1focal.20230527.034906` | `f33e1d283fad94d8d7bcf059301792282b0dd4d7fea69bc0167a05ea80fa5674` |
| `ros-foxy-realsense2-camera-msgs` | `4.51.1-1focal.20230527.054107` | `250cfbf39cb01df44126a610578aca017b5e68987ebd45a2de0828c05204c5a7` |
| `ros-foxy-realsense2-camera` | `4.51.1-1focal.20230606.035542` | `07ba023eb1f6b169ec7cccdf6fdd08f35f12ca78d602e7934f67dd8e7afcb093` |

Package source:

```text
https://mirrors.tuna.tsinghua.edu.cn/ros2/ubuntu
```

The optional `ros-foxy-realsense2-description` package is deferred because it
is not required for the initial depth-only test.
