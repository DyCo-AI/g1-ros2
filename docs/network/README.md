# G1 Network Setup

The Unitree G1 uses a direct Ethernet connection for development traffic. The
PC Ethernet interface must have a unique address on the same subnet as the
robot before ping, DDS discovery, ROS topics, LiDAR multicast, or camera
multicast can work.

Reference: [Unitree G1 Quick Development](https://support.unitree.com/home/en/G1_developer/quick_development)

## Current Lab Configuration

| Item | Value |
| --- | --- |
| Robot IP | `192.168.123.161` |
| G1 Auxiliary PC 2 (Jetson NX) | `192.168.123.164` |
| Auxiliary PC username | `unitree` |
| PC Ethernet IP | `192.168.123.222/24` |
| Subnet mask | `255.255.255.0` |
| Robot-facing PC interface | `enp0s31f6` |
| IPv4 gateway | Empty |

The PC address does not have to end in `.222`, but it must be an unused address
in `192.168.123.0/24`. Never assign the robot's `.161` address to the PC.

## 1. Put the Robot in Development Mode

Complete the [wireless controller startup](../controller/README.md), using
**Path B: Development Mode for Host-PC Work**. In short:

1. Support the G1 on the gantry and clear the surrounding area.
2. Power on the battery with one press followed by a second press and hold.
3. Wait for startup, then press `L2 + R2`.
4. Confirm the robot's development-mode LED is green.
5. Use `L2 + A` only if the forward arm/hand development pose is needed;
   `L2 + B` cancels that pose.

The green LED and expected supported robot behavior are the primary checks at
this stage. ROS service-state checks are available only after networking and
DDS are working.

## 2. Identify the Robot Ethernet Interface

Connect the LAN cable, then run:

```bash
ip -brief link
nmcli device status
```

Find the wired interface that changes to `UP` or `connected` when the cable is
inserted. The current lab interface is `enp0s31f6`.

Find the NetworkManager connection profile attached to that interface:

```bash
nmcli -f NAME,TYPE,DEVICE connection show --active
```

The connection name is often `Wired connection 1`, but it is not necessarily
the same as the interface name.

## 3. Configure the Static PC Address Once

Replace `<wired-connection>` with the connection name reported above:

```bash
sudo nmcli connection modify "<wired-connection>" \
  ipv4.method manual \
  ipv4.addresses 192.168.123.222/24 \
  ipv4.gateway "" \
  ipv4.never-default yes

sudo nmcli connection up "<wired-connection>"
```

`ipv4.never-default yes` prevents the robot-only LAN from replacing the PC's
normal internet route. NetworkManager saves this configuration, so it usually
does not need to be repeated after reboot.

For a temporary configuration that lasts only until the interface or machine
is restarted:

```bash
sudo ip address replace 192.168.123.222/24 dev enp0s31f6
sudo ip link set enp0s31f6 up
```

## 4. Verify the Address Every Session

```bash
ip -4 address show dev enp0s31f6
ip route get 192.168.123.161
```

Expected results include:

```text
inet 192.168.123.222/24
192.168.123.161 dev enp0s31f6 src 192.168.123.222
```

The static address is normally configured once. Address, route, and ping are
checked every time before robot work.

## 5. Ping the Robot Every Session

```bash
ping -c 4 192.168.123.161
```

A passing result has four replies and `0% packet loss`. Do not start ROS or the
diagnostics bridge if ping fails.

## 6. SSH into the G1 Jetson NX

The G1 Auxiliary PC 2 is the onboard Jetson NX connected to sensors such as
the Intel RealSense D435i. Confirm it is reachable from the user PC:

```bash
ping -c 4 192.168.123.164
```

Connect with the Unitree account:

```bash
ssh unitree@192.168.123.164
```

On the first connection, SSH displays the host-key fingerprint and asks
whether to trust it. Confirm the address is `192.168.123.164`, verify the
fingerprint against the lab record when available, and enter `yes` once. SSH
then saves the host key in the user PC's `~/.ssh/known_hosts` file.

The factory-default account is:

| Field | Factory default |
| --- | --- |
| Username | `unitree` |
| Password | `123` |

Treat `123` only as a factory bootstrap password. Change it for a deployed lab
robot and store the active credential in the lab's credential manager rather
than this repository.

The onboard login asks which ROS environment to use:

```text
ros:foxy(1) noetic(2) ?
```

Select `1` for ROS 2 Foxy or `2` for ROS 1 Noetic. Do not source both
distributions in the same ordinary shell. Verify the selected environment:

```bash
echo "$ROS_DISTRO"
echo "$ROS_VERSION"
```

Exit the onboard computer with:

```bash
exit
```

The `.161` MCU and `.164` auxiliary PC have different roles: ping `.161` to
verify the primary robot LAN connection, and SSH to `.164` for explicitly
approved onboard sensor or software diagnostics.

## 7. Configure CycloneDDS for the Robot Interface

The workspace configuration binds CycloneDDS to the robot-facing interface:

```text
config/cyclonedds_g1.xml
```

Current interface entry:

```xml
<NetworkInterface name="enp0s31f6" priority="default" multicast="default"/>
```

If the PC uses another interface, update that name before starting ROS. Then
source the DDS environment:

```bash
cd ~/g1-ros2
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI="file://${PWD}/config/cyclonedds_g1.xml"
```

## 8. Verify ROS Communication

After sourcing ROS, Unitree messages, and the workspace:

```bash
ros2 topic list
ros2 topic info /lf/lowstate
ros2 topic hz /lf/lowstate
```

Optional development/service-state check:

```bash
ros2 topic info /servicestate
ros2 topic echo --once /servicestate
```

On the current setup, an empty or inactive service state is used as a secondary
indication that the normal `ai_sport` service is not active. Do not use this as
the only development-mode check; firmware behavior can differ.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| No Ethernet interface | Cable, adapter power, link LEDs, and `ip -brief link` |
| Address missing after reboot | NetworkManager profile and `nmcli connection show` |
| Ping says unreachable | PC address, `/24` prefix, robot power, development mode, and route |
| Ping uses the wrong interface | `ip route get 192.168.123.161` and duplicate subnet routes |
| Ping works but ROS topics are absent | CycloneDDS URI, interface name, Unitree message workspace, and RMW implementation |
| ROS works but camera is empty | Camera multicast interface and GStreamer dependencies |
| Wi-Fi internet stops working | Confirm `ipv4.never-default yes` on the robot wired profile |

Avoid permanently disabling the firewall or Wi-Fi as a first fix. Verify the
specific interface and route first.

## Passing Network Check

- [ ] Robot is safely supported and in development mode.
- [ ] Development-mode LED is green.
- [ ] Robot-facing interface is connected.
- [ ] PC has `192.168.123.222/24` on that interface.
- [ ] Route to `192.168.123.161` uses that interface.
- [ ] Ping reports `0% packet loss`.
- [ ] G1 Auxiliary PC `192.168.123.164` is reachable when onboard access is
  required.
- [ ] `/lf/lowstate` is visible after sourcing ROS and CycloneDDS.
