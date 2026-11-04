# G1 Pilot Test Roadmap

This directory is the canonical release and acceptance-test plan for the lab's
Unitree G1. Keep implementation details in the subsystem runbooks and use this
page to define test order, required evidence, pass criteria, and release gates.

The tests are intentionally separated:

- **V1 Diagnostics Pilot:** read-only boot, hardware discovery, sensor checks,
  visualization, recording, and offline replay.
- **V2 Basic Teleoperation Pilot:** an explicitly motion-enabled test built on
  a passing V1 result.

Do not add motion commands to the V1 diagnostics path.

## Documentation Structure

Use one source of truth for both GitHub and a future GitHub Pages site:

```text
README.md                         Project landing page and quick start
docs/
  index.md                       Future documentation-site home
  pilots/
    README.md                    Versioned acceptance-test roadmap
    v1-diagnostics.md            V1 operator procedure and result sheet
    v2-basic-teleop.md           V2 operator procedure and result sheet
  bringup/README.md              Shared robot boot and shutdown procedure
  network/README.md              LAN, IP, ping, DDS, and SSH
  hardware/README.md             Robot variant and hardware manifest
  camera/README.md               RGB and RealSense diagnostics
  lidar/README.md                Mid360 diagnostics
  imus/README.md                 IMU diagnostics
  dex3/README.md                 Dex3 diagnostics and calibration
  rerun/README.md                Rerun operation and troubleshooting
  robot-state/README.md          Joint and motor telemetry
  health/README.md               Battery, alarms, board, and safety state
  controls/README.md             Controller input and command ownership
  reference/topics.md            Topic/type/rate/QoS inventory
  reference/datasets.md          MCAP/RRD profiles and metadata schema
```

The root `README.md` should contain only the project purpose, one dashboard
screenshot, supported hardware, quick start, current release status, and links
to the runbooks. Detailed commands, calibration data, and troubleshooting
belong in `docs/`.

## V1: Read-Only Diagnostics Pilot

### Goal

A new lab user can connect a supported G1, run one command, receive a clear
pass/warn/fail report, inspect all supported streams in Rerun, record a short
dataset, shut down cleanly, and replay the result without the robot connected.

### Implementation TODO

#### Repository and installation

- [ ] Initialize the repository, create the baseline commit, and connect it to
  the lab GitHub organization when the team is ready to publish.
- [ ] Pin ROS, Python, Rerun, GStreamer, and system dependencies.
- [ ] Add a clean-machine installation procedure and dependency checker.
- [ ] Add versioned YAML profiles for the lab's G1 29-DOF + Dex3 configuration.
- [ ] Add license and provenance notes for Unitree messages, URDFs, and meshes.

#### One-command preflight

- [ ] Add `scripts/g1_preflight.sh` or an equivalent ROS 2 command.
- [ ] Check development mode, gantry/support state confirmation, Ethernet
  interface, `192.168.123.222/24`, routing, robot ping, and Jetson reachability.
- [ ] Check ROS 2, CycloneDDS, Unitree message packages, Rerun, GStreamer, URDF
  assets, disk space, and write permissions.
- [ ] Check PC, robot, LiDAR, and Jetson clock agreement before recording.
- [ ] Emit concise `PASS`, `WARN`, and `FAIL` output plus a JSON result file.
- [ ] Refuse to continue on safety, network, DDS, or disk-space failures.

#### Stream readiness

- [ ] Create a read-only readiness node that checks topic name, message type,
  publisher count, QoS, observed rate, timestamp age, and basic sample validity.
- [ ] Cover low state, body motors, body IMU, secondary IMU, Mid360 cloud and
  IMU, both Dex3 hands, battery, board health, alarms, emergency stop, service
  state, and wireless controller input.
- [ ] Maintain expected-rate ranges by robot firmware/configuration rather than
  embedding unexplained constants in code.
- [ ] Produce a terminal summary and save the full measurements with the test
  artifacts.

#### Camera

- [ ] Finish read-only inspection of `master_service` and `videohub_pc4`
  lifecycle behavior on the onboard Jetson.
- [ ] Implement explicit camera modes: `stock`, `realsense`, and `off`.
- [ ] Guarantee restoration of the stock Unitree video process after normal
  exit, failure, or `Ctrl+C`.
- [ ] Add native RealSense RGB, depth, and `CameraInfo` to the ROS/Rerun path.
- [ ] Validate camera topics, frame rate, resolution, QoS, timestamp behavior,
  latency, `/dev/video*` ownership, and recovery after repeated launches.

#### LiDAR and IMUs

- [ ] Validate Mid360 point rate, point count, fields, timestamps, packet loss,
  QoS, frame name, and transform to the G1 model.
- [ ] Verify point-cloud attachment while the robot pose changes.
- [ ] Validate body, secondary, Mid360, and optional Dex3 IMU rates, units,
  frame conventions, covariance validity, stationary noise, and drift.
- [ ] Record measured sensor extrinsics and uncertainty in the hardware runbook.

#### Dex3

- [ ] Run baseline calibration on both physical hands.
- [ ] Verify tactile packet IDs `0..8` and all `pressure[12]` indices against the
  Unitree diagrams.
- [ ] Confirm each physical pad activates the expected Rerun region and returns
  near baseline after release.
- [ ] Verify all physical finger movements animate the expected URDF joints.
- [ ] Save calibration output with robot/hand identity and calibration date.

#### Rerun operator interface

- [ ] Add visible subsystem health, stale-stream, battery, alarm, camera-mode,
  and recording-state indicators.
- [ ] Provide a compact operator layout and a separate detailed engineering
  layout.
- [ ] Bound image, point-cloud, and scalar logging so long sessions do not grow
  memory without limit.
- [ ] Verify every default panel from a clean terminal and document expected
  output with current screenshots.

#### Recording and replay

- [ ] Add a 10-second smoke-test command that records raw ROS data to MCAP and
  the visualization to RRD.
- [ ] Define `minimal`, `full-diagnostics`, and `camera-depth` recording
  profiles.
- [ ] Store a manifest containing hardware configuration, clamp state,
  firmware, topic inventory, calibration IDs, command line, test result, and
  clock status.
- [ ] Add an offline replay command that works with the robot disconnected.
- [ ] Verify message counts, rates, duration, image decoding, point clouds,
  URDF animation, and tactile data after replay.
- [ ] Commit a small sanitized fixture dataset for automated tests, or publish
  it as a versioned release asset if it is too large for Git.

#### Testing and documentation

- [ ] Add unit tests for joint mapping, tactile packet mapping, tactile
  processing, image conversion, and readiness thresholds.
- [ ] Add an offline integration test using the fixture dataset.
- [ ] Add linting and CI before the first lab GitHub release.
- [ ] Write the final `v1-diagnostics.md` operator procedure with expected
  output, troubleshooting, shutdown, and a result sheet.
- [ ] Have a user who did not develop the system run V1 from a clean terminal.
- [ ] Record the first accepted V1 result and tag the release `v1.0.0`.

### V1 Pass Criteria

- [ ] No command-capable ROS publisher is created by the V1 process.
- [ ] Preflight reports no blocking failures.
- [ ] Every required stream passes its configured presence, rate, timestamp,
  and validity checks, or is explicitly marked unsupported for this hardware.
- [ ] Rerun shows the live URDF, LiDAR, selected camera mode, body IMU, and both
  Dex3 hands without repeated transform or missing-entity errors.
- [ ] A 10-second MCAP and RRD pair is recorded and replayed offline.
- [ ] Shutdown restores vendor services and leaves no orphan process.
- [ ] The test report and hardware manifest are saved with the dataset.

## V2: Basic Teleoperation Pilot

### Entry Gate

V2 may start only after the same-session V1 preflight passes. Diagnostics and
recording remain read-only observers; teleoperation runs as a separate,
explicitly enabled command path.

### Recommended Initial Scope

Start with bounded upper-body and Dex3 teleoperation while the robot is
supported on the gantry. Treat locomotion as a later test with its own safety
review rather than including it in the first teleoperation milestone.

### Implementation TODO

- [x] Add the initial `g1_teleop` package with transport-independent Dex3
  motion tests and a native SDK2 hardware executable that is read-only unless
  `--enable-motion` is supplied.
- [x] Preserve the guarded internal Dex3 prototype as provenance for the first
  lab hand test and document its migration into `src/g1_teleop`.
- [ ] Run the one-hand-at-a-time right and left Dex3 hardware acceptance
  sequence and review the generated command-versus-measured logs.
- [ ] Select and document the supported Unitree SDK2 command interface for this
  exact robot and firmware; do not assume third-party action servers exist.
- [ ] Document controller ownership, mode transitions, leases, watchdogs,
  command rate, and the procedure for returning control to Unitree software.
- [ ] Record whether the hip clamp is installed and reject incompatible active
  DOF/controller configurations.
- [ ] Map controller inputs to a small allowlist of joints and Dex3 actions.
- [ ] Add deadman enable, emergency stop, command timeout, joint-position
  limits, velocity limits, acceleration limits, and workspace limits.
- [ ] Add `--dry-run` and explicit `--enable-motion` modes; motion must never be
  enabled by configuration accident.
- [ ] Test command generation without hardware, then with the robot supported
  on the gantry and an operator at the emergency stop.
- [ ] Record input commands, post-limit commands, measured state, safety state,
  and all V1 sensor streams to MCAP/RRD.
- [ ] Compare commanded and measured motion and report tracking error,
  saturation, dropped commands, watchdog events, and stop latency.
- [ ] Verify release of the deadman switch, process failure, network loss, and
  operator stop all produce the reviewed safe behavior.
- [ ] Write `v2-basic-teleop.md`, including a signed test checklist and rollback
  procedure.

### V2 Pass Criteria

- [ ] V1 passes immediately before motion is enabled.
- [ ] Exactly one reviewed process owns the command interface.
- [ ] Motion remains within the approved joint/workspace envelope.
- [ ] Every stop path is tested and its latency recorded.
- [ ] Commanded and measured state replay correctly with the robot disconnected.
- [ ] Vendor control is restored cleanly after the test.

## GitHub Pages Plan

Use **MkDocs Material** as the documentation generator when the repository is
moved to the lab GitHub organization. It works well for a runbook-heavy robotics
repository and keeps ordinary Markdown readable directly in GitHub.

Implementation TODO:

- [ ] Add `mkdocs.yml` with navigation ordered as: Start Here, V1 Pilot, V2
  Pilot, Bring-up, Hardware, Sensors, Visualization, Recording, Reference, and
  Troubleshooting.
- [ ] Add `docs/index.md` as the documentation-site landing page.
- [ ] Keep all commands and procedures in the repository; do not maintain a
  separate hand-edited wiki with duplicated content.
- [ ] Add GitHub Actions to build the docs on pull requests and deploy Pages
  from the protected default branch.
- [ ] Enable strict link checking so renamed runbooks fail CI instead of
  silently breaking navigation.
- [ ] Store screenshots under `docs/assets/` and use descriptive names and alt
  text.
- [ ] Keep large MCAP/RRD datasets out of Git; publish sanitized examples as
  release assets or in approved lab storage and link them by version/checksum.
- [ ] Add ownership/review rules for safety procedures, hardware manifests, and
  motion tests.

## Maintenance Rules

1. A subsystem page owns its detailed commands and troubleshooting.
2. A pilot page links to subsystem pages instead of copying their contents.
3. Every test states prerequisites, exact command, expected output, pass
   criteria, artifacts, shutdown, and recovery.
4. Hardware- or firmware-specific facts include the observed version and date.
5. Motion procedures require review separate from read-only diagnostics.
6. Documentation changes are reviewed with the code or hardware change that
   made them necessary.
