# G1 Hardware Configuration

This page records physical configurations that change which robot degrees of
freedom a controller may use. Treat the physical configuration as part of the
controller contract, dataset metadata, and motion-test preflight.

## Unitree References

- [Unitree G1 Developer documentation](https://support.unitree.com/home/en/G1_developer)
- [Unitree G1 Dex3 dexterous-hand documentation](https://support.unitree.com/home/en/G1_developer/dexterous_hand)

Use Unitree documentation and component manufacturer documentation for
specifications, installation limits, and maintenance procedures. Record the
firmware and hardware revision used by the lab because current documentation
may describe a different revision.

## Lab Hardware Inventory

The known high-level configuration is:

| Subsystem | Current lab hardware | Status |
| --- | --- | --- |
| Robot | Unitree G1, 29-DOF body configuration | Verify exact model/revision |
| Hands | Left and right Unitree Dex3 | Installed; record revisions and serials |
| Front depth camera | Intel RealSense D435i | USB-detected on auxiliary PC |
| LiDAR | Livox Mid360 | ROS 2 point-cloud and IMU streams observed |
| Auxiliary computer | NVIDIA Jetson NX-class module, Ubuntu 20.04 ARM64 | Verify exact module, RAM, storage, and JetPack/L4T |
| Robot controller/MCU | Unitree controller at `192.168.123.161` | Record firmware version |
| Auxiliary PC network | `192.168.123.164` | See [network runbook](../network/README.md) |
| Hip clamp | Physical configurable DOF constraint | Exact part and constrained joints TODO |

## Hardware Documentation TODO

### Robot Identity and Configuration

- [ ] Record the lab asset ID, robot serial number, exact G1 order code, body
  DOF variant, manufacturing date, and purchase/configuration options.
- [ ] Record installed firmware versions, update history, controller mode
  compatibility, and the procedure used to query each version.
- [ ] Record the canonical URDF/mesh revision and a hash of the model used by
  diagnostics, simulation, retargeting, and controllers.
- [ ] Maintain a joint-name-to-motor-ID table with limits, zero offsets, drive
  type, and whether each joint is active or mechanically constrained.

### Auxiliary NVIDIA Computer

- [ ] Record the exact Jetson module and carrier-board model, serial number,
  RAM, storage, JetPack/L4T version, CUDA version, kernel, and architecture.
- [ ] Document physical Ethernet, USB, display, storage, and power connections.
- [ ] Record the stock Unitree services, boot dependencies, disk usage, thermal
  limits, and a backup/restore procedure before installing lab software.
- [ ] Document which software belongs to Unitree and which is maintained by the
  lab; keep lab packages in isolated workspaces or containers where possible.

### Intel RealSense D435i

- [ ] Record serial number, firmware version, USB port/bus, supported and chosen
  RGB/depth/IMU profiles, and the software used to query them.
- [ ] Document the camera mount, optical-frame convention, measured transform
  to the G1 body, calibration files, calibration date, and file hashes.
- [ ] Record which `/dev/video*` endpoints correspond to color, depth,
  infrared, metadata, and IMU interfaces.
- [ ] Document ownership conflicts with Unitree's `videohub_pc4`, including
  which endpoint it opens and which streams can safely run concurrently.
- [ ] Add inspection and cleaning guidance for the lenses, depth emitters,
  connector, and cable strain relief from authoritative sources.

### Livox Mid360

- [ ] Record serial number, firmware, IP configuration, Ethernet interface,
  calibration/extrinsic files, return mode, scan rate, and time source.
- [ ] Document the physical mount and measured transform to the G1 body and
  camera, including frame-axis conventions and uncertainty.
- [ ] Record expected point count/rate, IMU rate, timestamps, packet loss, power
  path, connector, cable routing, and startup behavior.
- [ ] Document lens/window inspection and cleaning guidance from Livox.

### Dex3 Hands

- [ ] Record left/right hand serial numbers, hardware revisions, firmware,
  joint/motor IDs, limits, zero positions, communication interfaces, and power
  requirements.
- [ ] Record the tactile packet IDs, `pressure[12]` index geometry, valid raw
  range, invalid sentinel, scale, calibration procedure, temperature fields,
  and known dead/noisy taxels for each hand.
- [ ] Document hand-to-wrist mounting, connector orientation, cable routing,
  replacement procedure, and the exact URDF hand revision.
- [ ] Link each verified detail to the corresponding
  [Dex3 diagnostic procedure](../dex3/README.md) and Unitree source page.

### Lab Operations and Maintenance

- [ ] Create a cable/connector map with labeled photographs and approved spare
  part numbers.
- [ ] Track calibration dates, maintenance, repairs, component replacements,
  observed faults, and the dataset runs affected by each change.
- [ ] Record battery variants, charger, safe operating limits, storage state,
  cycle count where available, and inspection procedure.
- [ ] Add mass, center-of-mass, payload, mounting-hole, and workspace limits
  needed by simulation and controller validation.
- [ ] Add a configuration manifest captured with every dataset: robot and
  sensor serials, firmware, calibration hashes, URDF hash, clamp state, active
  DOFs, controller version, and operator.

## Hip Clamp

The lab has a physical hip clamp that can be mounted to the G1 to isolate one
or more hip/waist degrees of freedom. Whether it is installed depends on the
requirements and assumptions of the controller being tested.

A mounted clamp changes the mechanism. Software must not command a physically
constrained joint, and a controller validated with the clamp installed must not
be assumed safe with it removed. The URDF, active-joint list, command mask,
state estimator, safety limits, and recorded metadata must all agree with the
real hardware configuration.

Do not use the hip clamp as an emergency stop or as a substitute for controller
limits. Installation and removal must follow the approved manufacturer or lab
procedure with the robot safely supported and in the required powered/torque
state.

## Pre-Motion Check

Before enabling any motion controller:

- [ ] Identify the controller and robot hardware variant.
- [ ] Determine whether that controller requires the hip clamp installed or
  removed.
- [ ] Visually verify and record the actual clamp state.
- [ ] Verify the exact constrained joint names and motor IDs.
- [ ] Confirm constrained joints p the robot supported on the gantry for the initial controller test.are omitted or masked from outgoing commands.
- [ ] Confirm the controller model and state estimator use the same active DOFs.
- [ ] Check clamp installation, fasteners, clearances, and cable routing using
  the approved procedure.
- [ ] Record the clamp state and active-DOF configuration with the dataset.
- [ ] Keep the robot supported on the gantry for the initial controller test.

Suggested dataset metadata:

```yaml
robot_variant: g1_29dof_dex3
hip_clamp_installed: true  # or false
constrained_joints: []     # populate with verified joint names
controller: ""
controller_version: ""
hardware_check_operator: ""
```

## Controller Compatibility Record

Complete this table before hardware controller testing:

| Controller | Clamp state | Constrained joints/IDs | Robot variant | Validated by/date |
| --- | --- | --- | --- | --- |
| Minimal motion smoke test | TODO | TODO | G1 29-DOF + Dex3 | TODO |
| G1Pilot teleoperation | TODO | TODO | G1 29-DOF + Dex3 | TODO |
| Blind locomotion controller | TODO | TODO | G1 29-DOF + Dex3 | TODO |
| Upper-body retargeting | TODO | TODO | G1 29-DOF + Dex3 | TODO |

## TODO

- [ ] Record the clamp manufacturer, part number, revision, and source manual.
- [ ] Identify exactly which joint names and motor IDs each mounting
  configuration constrains.
- [ ] Add clear installed/removed photographs and orientation markers.
- [ ] Document the approved installation and removal procedure.
- [ ] Record required tools, fastener torque values, and inspection criteria
  from an authoritative source.
- [ ] Add a software preflight that rejects motion when the declared clamp
  state and controller active-DOF configuration are incompatible.
- [ ] Include clamp state in MCAP metadata, Rerun recordings, and motion-test
  reports.
