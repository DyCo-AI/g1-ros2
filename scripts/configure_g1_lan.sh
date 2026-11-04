#!/usr/bin/env bash
set -euo pipefail

DEFAULT_INTERFACE="enp0s31f6"
DEFAULT_PC_ADDR="192.168.123.222/24"
DEFAULT_ROBOT_IP="192.168.123.161"

usage() {
  cat <<USAGE
Configure the PC Ethernet interface for Unitree G1 LAN diagnostics.

Usage:
  sudo ./scripts/configure_g1_lan.sh [interface] [pc-cidr] [robot-ip]

Defaults:
  interface: ${DEFAULT_INTERFACE}
  pc-cidr:   ${DEFAULT_PC_ADDR}
  robot-ip:  ${DEFAULT_ROBOT_IP}

Example:
  sudo ./scripts/configure_g1_lan.sh enp0s31f6 192.168.123.222/24 192.168.123.161

The PC IP must be unique. It should be on the same subnet as the robot, not the
same exact IP as the robot.
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

IFACE="${1:-$DEFAULT_INTERFACE}"
PC_ADDR="${2:-$DEFAULT_PC_ADDR}"
ROBOT_IP="${3:-$DEFAULT_ROBOT_IP}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "This script changes network settings. Run it with sudo:" >&2
  echo "  sudo $0 ${IFACE} ${PC_ADDR} ${ROBOT_IP}" >&2
  exit 1
fi

if ! ip link show "${IFACE}" >/dev/null 2>&1; then
  echo "Interface '${IFACE}' was not found." >&2
  echo "Run 'ip link' or 'ifconfig' and pass the robot-facing interface name." >&2
  exit 1
fi

echo "Configuring ${IFACE} for Unitree G1 LAN..."
echo "  PC address: ${PC_ADDR}"
echo "  Robot IP:   ${ROBOT_IP}"

configure_with_nmcli() {
  local connection_name

  if ! command -v nmcli >/dev/null 2>&1; then
    return 1
  fi

  connection_name="$(nmcli -g GENERAL.CONNECTION device show "${IFACE}" | head -n 1)"
  if [[ -z "${connection_name}" || "${connection_name}" == "--" ]]; then
    return 1
  fi

  echo "Using NetworkManager connection: ${connection_name}"
  nmcli connection modify "${connection_name}" \
    ipv4.method manual \
    ipv4.addresses "${PC_ADDR}" \
    ipv4.never-default yes \
    ipv6.method ignore

  nmcli connection modify "${connection_name}" ipv4.gateway "" >/dev/null 2>&1 || true
  nmcli connection up "${connection_name}"
}

configure_with_ip() {
  echo "NetworkManager connection was not available; using temporary ip commands."
  echo "This fallback lasts until the interface is reconfigured or the PC reboots."
  ip link set "${IFACE}" up
  ip addr flush dev "${IFACE}"
  ip addr add "${PC_ADDR}" dev "${IFACE}"
}

if ! configure_with_nmcli; then
  configure_with_ip
fi

echo
echo "Current address on ${IFACE}:"
ip -brief addr show "${IFACE}"

echo
echo "Pinging robot..."
ping -c 4 -W 1 "${ROBOT_IP}"

echo
echo "G1 LAN check passed."
