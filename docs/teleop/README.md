# G1 Basic Teleoperation

This runbook covers the first motion-enabled test in `g1-ros`: a bounded,
one-hand-at-a-time Dex3 connectivity smoke test. Whole-body and locomotion
control are out of scope.

The motion test is separate from the read-only diagnostics processes. Run the
V1 preflight and Rerun diagnostics first, then start this command explicitly.

## Safety Boundary

Before using `--enable-motion`:

1. Put the G1 on the gantry and keep the controller/emergency stop available.
2. Enter the reviewed development pose and wait for the robot to become still.
3. Empty the selected hand and clear the complete finger sweep.
4. Confirm that no other Dex3 controller or command publisher is running.
5. Start with one hand. Do not run left and right smoke tests concurrently.

The program does not change the robot mode, command the arms, command the
torso, or command locomotion. Hand gains are not calibrated force limits.
Handled faults attempt a zero-effort release, but process kills, transport
loss, and power loss cannot guarantee delivery.

## Provenance

The guarded control sequence was adapted from the lab's validated prototype:

```text
/home/sriramk/g1_holloween/sdk_dex3_basic
```

It uses the official native Unitree SDK2 `HandCmd_` and `HandState_` types. The
motion signs and limits follow Unitree's G1 Dex3 example and are covered by
offline tests in `src/g1_teleop/test/`.

Although it is launched with `ros2 run` for workspace consistency, the hardware
process itself uses native SDK2 rather than `rclcpp`. Its launcher gives SDK2's
matched CycloneDDS libraries precedence over libraries from the sourced ROS
environment.

## SDK Dependency

`g1_teleop` does not vendor another SDK copy. Set `UNITREE_SDK2_DIR` to an
official Unitree SDK2 source tree before building the hardware executable.

For the currently archived, checksum-verified lab copy:

```bash
mkdir -p ~/unitree_g1_ws/third_party/unitree_sdk2
tar -xzf ~/g1_holloween/data/unitree_sdk2_g1_reference.tar.gz \
  --strip-components=1 \
  -C ~/unitree_g1_ws/third_party/unitree_sdk2
export UNITREE_SDK2_DIR=~/unitree_g1_ws/third_party/unitree_sdk2
```

The extracted SDK directory is a local dependency and should not be committed
to this repository. Record the SDK revision and license before the first lab
release.

Build the package:

```bash
cd ~/unitree_g1_ws
source /opt/ros/humble/setup.bash
export UNITREE_SDK2_DIR=~/unitree_g1_ws/third_party/unitree_sdk2
colcon build --packages-select g1_teleop \
  --cmake-args -DUNITREE_SDK2_DIR="$UNITREE_SDK2_DIR"
source install/setup.bash
```

If `UNITREE_SDK2_DIR` is absent, the package deliberately builds only its
transport-independent motion tests. It does not install `dex3_smoke`.

## Step 1: Read-Only Check

Always run without `--enable-motion` first:

```bash
ros2 run g1_teleop dex3_smoke enp0s31f6 --side right
```

Expected result:

```text
PASS: read-only feedback check completed; no command publisher was created.
```

Repeat for the left hand:

```bash
ros2 run g1_teleop dex3_smoke enp0s31f6 --side left
```

This verifies fresh state packets, seven finite motor positions, hand error
words, approximate position-derived velocity, and the side-specific limits.

## Step 2: Bounded Motion Check

Only after the read-only check and safety checklist pass:

```bash
ros2 run g1_teleop dex3_smoke enp0s31f6 \
  --side right \
  --enable-motion
```

The process remains disengaged until an operator types a command and presses
Enter:

| Command | Behavior |
| --- | --- |
| `o` | Open the six flexion joints by at most 10 degrees over six seconds. |
| `c` | Close the six flexion joints by at most 10 degrees over six seconds. |
| `r` | Return to the measured position captured at first engagement. |
| `p` | Print measured positions. |
| `s`, `q` | Attempt zero-effort release and exit. |

Motor 0, thumb opposition, stays at its captured position. Repeated moves are
limited to 30 degrees around the captured start and by the side-specific joint
limits. A new move is rejected until the prior move settles.

The process stops on stale feedback, a hand error word, excessive estimated
speed, a control-loop stall, tracking error, settling timeout, competing
command traffic observed before engagement, or operator idle timeout.

Each engaged session writes a CSV containing command and measured positions.
This CSV is diagnostic evidence, not the final dataset format. MCAP and RRD
capture will be added to the V2 pilot workflow.

## Initial Hardware Acceptance Sequence

Run each line as a separate process:

1. Right hand read-only check.
2. Right hand: `o`, wait for `SETTLED`, `c`, wait, `r`, wait, then `s`.
3. Left hand read-only check.
4. Left hand: `o`, wait for `SETTLED`, `c`, wait, `r`, wait, then `s`.
5. Confirm the physical direction, Rerun URDF direction, measured travel, and
   tactile stream for each hand.

Do not proceed to controller buttons, dual-hand commands, arms, or torso until
this sequence passes and its logs have been reviewed.

## Remaining Work

- [ ] Extract and record the exact Unitree SDK2 revision used by the lab.
- [ ] Load a validated hardware profile at runtime instead of compiling the
  initial reviewed constants into the executable.
- [ ] Run and document the right-hand hardware acceptance sequence.
- [ ] Run and document the left-hand hardware acceptance sequence.
- [ ] Add a machine-readable pass/fail summary.
- [ ] Add command-target telemetry to Rerun.
- [ ] Record synchronized MCAP and RRD data during the test.
- [ ] Add offline replay and commanded-versus-measured plots.
- [ ] Add deadman-controlled gamepad input after deterministic tests pass.
- [ ] Review the separate `arm_sdk` upper-body controller before adding arm or
  torso motion.
