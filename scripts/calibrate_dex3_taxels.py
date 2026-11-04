#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import rclpy
from rclpy.node import Node
from unitree_hg.msg import HandState


PAD_ORDER = {
    "thumb": [0, 1],
    "finger_1": [4, 5],
    "finger_2": [2, 3],
    "palm": [6, 7, 8],
}


class Dex3TaxelCalibrator(Node):
    def __init__(self, left_topic: str, right_topic: str) -> None:
        super().__init__("dex3_taxel_calibrator")
        self.latest: dict[str, HandState] = {}
        self.create_subscription(HandState, left_topic, lambda msg: self._on_hand("left", msg), 10)
        self.create_subscription(HandState, right_topic, lambda msg: self._on_hand("right", msg), 10)

    def _on_hand(self, side: str, msg: HandState) -> None:
        self.latest[side] = msg


def pressure_matrix(msg: HandState) -> np.ndarray:
    rows = []
    for sensor in msg.press_sensor_state:
        rows.append([float(value) for value in sensor.pressure])
    if not rows:
        return np.empty((0, 12), dtype=np.float32)
    return np.asarray(rows, dtype=np.float32)


def valid_mask(
    raw: np.ndarray,
    valid_min: float,
    invalid_value: float,
    invalid_tolerance: float,
) -> np.ndarray:
    return (
        np.isfinite(raw)
        & (raw >= valid_min)
        & (np.abs(raw - invalid_value) > invalid_tolerance)
    )


def collect_samples(
    node: Dex3TaxelCalibrator,
    side: str,
    sample_count: int,
    timeout_s: float,
) -> list[np.ndarray]:
    samples = []
    deadline = time.monotonic() + timeout_s
    while len(samples) < sample_count and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.1)
        msg = node.latest.get(side)
        if msg is not None:
            samples.append(pressure_matrix(msg))
    return samples


def collect_for_duration(
    node: Dex3TaxelCalibrator,
    side: str,
    duration_s: float,
) -> list[np.ndarray]:
    samples = []
    deadline = time.monotonic() + duration_s
    while time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.05)
        msg = node.latest.get(side)
        if msg is not None:
            samples.append(pressure_matrix(msg))
    return samples


def compute_baseline(
    samples: list[np.ndarray],
    valid_min: float,
    invalid_value: float,
    invalid_tolerance: float,
) -> np.ndarray:
    if not samples:
        return np.full((9, 12), valid_min, dtype=np.float32)

    valid_samples = []
    for sample in samples:
        valid = valid_mask(sample, valid_min, invalid_value, invalid_tolerance)
        valid_samples.append(np.where(valid, sample, np.nan))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        baseline = np.nanmedian(np.stack(valid_samples, axis=0), axis=0)
    return np.nan_to_num(baseline, nan=valid_min)


def strongest_response(
    samples: list[np.ndarray],
    baseline: np.ndarray,
    valid_min: float,
    invalid_value: float,
    invalid_tolerance: float,
    scale: float,
) -> dict:
    if not samples:
        return {"sensor_id": None, "taxel_id": None, "value": 0.0, "sensor_scores": []}

    maxima = np.zeros_like(baseline, dtype=np.float32)
    for sample in samples:
        valid = valid_mask(sample, valid_min, invalid_value, invalid_tolerance)
        delta = np.where(valid, np.maximum(sample - baseline, 0.0) / scale, 0.0)
        maxima = np.maximum(maxima, delta)

    sensor_scores = np.max(maxima, axis=1) if maxima.size else np.asarray([], dtype=np.float32)
    if sensor_scores.size == 0:
        return {"sensor_id": None, "taxel_id": None, "value": 0.0, "sensor_scores": []}

    sensor_id = int(np.argmax(sensor_scores))
    taxel_id = int(np.argmax(maxima[sensor_id]))
    return {
        "sensor_id": sensor_id,
        "taxel_id": taxel_id,
        "value": float(maxima[sensor_id, taxel_id]),
        "sensor_scores": [float(value) for value in sensor_scores],
    }


def side_sequence(selected: str) -> list[str]:
    if selected == "both":
        return ["left", "right"]
    return [selected]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Guided Dex3 tactile baseline and packet-ID validation."
    )
    parser.add_argument("--side", choices=["left", "right", "both"], default="both")
    parser.add_argument("--left-topic", default="/lf/dex3/left/state")
    parser.add_argument("--right-topic", default="/lf/dex3/right/state")
    parser.add_argument("--baseline-samples", type=int, default=50)
    parser.add_argument("--touch-seconds", type=float, default=2.0)
    parser.add_argument("--valid-min", type=float, default=100000.0)
    parser.add_argument("--invalid-value", type=float, default=30000.0)
    parser.add_argument("--invalid-tolerance", type=float, default=1000.0)
    parser.add_argument("--scale", type=float, default=10000.0)
    parser.add_argument("--output-dir", default="datasets")
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()

    rclpy.init()
    node = Dex3TaxelCalibrator(args.left_topic, args.right_topic)
    report = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "baseline_samples": args.baseline_samples,
        "touch_seconds": args.touch_seconds,
        "results": [],
    }
    try:
        for side in side_sequence(args.side):
            input(f"Keep {side} hand untouched, then press Enter to collect baseline...")
            baseline_samples = collect_samples(node, side, args.baseline_samples, timeout_s=10.0)
            if len(baseline_samples) < args.baseline_samples:
                print(f"{side}: only collected {len(baseline_samples)} baseline samples")
            baseline = compute_baseline(
                baseline_samples,
                args.valid_min,
                args.invalid_value,
                args.invalid_tolerance,
            )

            for group, sensor_ids in PAD_ORDER.items():
                for expected_id in sensor_ids:
                    input(f"Touch {side} {group} ID {expected_id}, then press Enter...")
                    samples = collect_for_duration(node, side, args.touch_seconds)
                    response = strongest_response(
                        samples,
                        baseline,
                        args.valid_min,
                        args.invalid_value,
                        args.invalid_tolerance,
                        args.scale,
                    )
                    passed = response["sensor_id"] == expected_id
                    status = "PASS" if passed else "CHECK"
                    print(
                        f"{status}: expected ID {expected_id}, "
                        f"strongest ID {response['sensor_id']} "
                        f"taxel {response['taxel_id']} value {response['value']:.3f}"
                    )
                    report["results"].append(
                        {
                            "side": side,
                            "group": group,
                            "expected_id": expected_id,
                            "passed": passed,
                            **response,
                        }
                    )
    finally:
        node.destroy_node()
        rclpy.shutdown()

    if not args.no_save:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"dex3_taxel_calibration_{datetime.now():%Y%m%d_%H%M%S}.json"
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"saved {output_path}")


if __name__ == "__main__":
    main()
