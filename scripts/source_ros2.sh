#!/usr/bin/env bash
set -eo pipefail

source /opt/ros/humble/setup.bash
set -u

export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

echo "ROS_DISTRO=${ROS_DISTRO}"
echo "RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION}"
