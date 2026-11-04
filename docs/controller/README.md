# G1 Wireless Controller Startup

This page records the controller workflow used with the DyCo AI Lab G1. Keep
the robot supported on the gantry while learning these transitions. Controller
behavior can change with robot hardware and firmware, so do not apply this
mapping to another G1 without validating it first.

> [!WARNING]
> Use only the combinations and demos listed on this page. The lab robot has
> Dex3 tactile hands, while some stock controller motions were designed for
> the basic-hand configuration. An unknown motion can create unexpected hand,
> arm, body, or gantry contact.

## 1. Power On

1. Put the robot on the gantry and clear its full motion area.
2. Keep the wireless controller and emergency-stop access available.
3. On the battery power button, press once, then press again and hold.
4. Wait for the robot startup sequence to complete before sending a command.

## 2. Choose One Operating Path

Do not mix the two paths during a test. Return the robot to a known state
before changing paths.

### Path A: Stock Walking Controller and Known Demos

Use this path only for the stock Unitree walking controller and the small
allowlist of lab demos below:

1. Press `L2 + B` to enter **Damp** mode.
2. Press `L2 + D-pad Up` to enter **Stand** mode.
3. Press `R1 + Y` to enter **Ready** mode.

Ready mode leaves the Unitree walking controller active. It is a starting
state for supervised stock-controller operation, not for a host-PC controller
that expects Unitree's walking controller to be disabled.

The currently allowed stock demos are:

- Handshake
- Wave hand
- Face wave
- Right kiss
- Clap, only when specifically needed

Clap repeatedly brings the hands together and may cause cumulative damage.
Avoid it during routine demonstrations.

### Path B: Development Mode for Host-PC Work

Use this path for ROS 2 diagnostics, data collection, and lab controller
development:

1. Press `L2 + R2` to enter **Development** mode.
2. Confirm the development-mode LED is green.
3. Optionally press `L2 + A` to move both arms and hands to the forward
   development pose.
4. Press `L2 + B` to cancel that forward pose and return from it.

Entering Development mode disables the stock Unitree walking controller. In
this context, `L2 + B` cancels the `L2 + A` development pose; while the stock
walking controller is active in Path A, `L2 + B` selects Damp mode.

After entering Development mode, connect the host PC, run the mandatory ping
check, verify ROS state topics, and start the read-only diagnostics before any
motion-capable lab program.

## Prohibited and Untested Commands

- Do not use **Mode 8 / climb mode**.
- Do not use **Mode 9 / dance mode** or any dance motion.
- Do not try controller combinations or stock demos that are not explicitly
  listed above.
- Do not assume a basic-hand stock motion is safe for the installed Dex3
  hands.
- Do not send wireless-controller motion commands while a host-PC program owns
  a robot command interface.

## TODO

- [ ] Validate and record the robot firmware version for this mapping.
- [ ] Record the exact controller input for each allowed demo and its observed
  behavior with the lab's 29-DOF G1 and Dex3 hands.
- [ ] Verify controller ownership and service state for each transition using
  ROS 2 telemetry.
- [ ] Add an operator-observed pass/fail log for Damp, Stand, Ready, and
  Development transitions.
- [ ] Treat every other mode and demo as untested and not recommended until a
  separate risk review and gantry validation are complete.

