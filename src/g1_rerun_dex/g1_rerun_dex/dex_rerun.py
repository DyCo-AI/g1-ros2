from __future__ import annotations

import warnings
from typing import Iterable

import numpy as np
import rclpy
from rclpy.node import Node
from unitree_hg.msg import HandState

try:
    import cv2
except ImportError:  # pragma: no cover - labels are optional
    cv2 = None

try:
    import rerun as rr
    import rerun.blueprint as rrb
except ImportError:  # pragma: no cover - exercised on systems without rerun-sdk
    rr = None
    rrb = None


PAD_GROUPS = {
    "thumb": [0, 1],
    "finger_1": [4, 5],
    "finger_2": [2, 3],
    "palm": [6, 7, 8],
}


class DexRerun(Node):
    def __init__(self) -> None:
        super().__init__("g1_rerun_dex")

        self.declare_parameter("left_topic", "/lf/dex3/left/state")
        self.declare_parameter("right_topic", "/lf/dex3/right/state")
        self.declare_parameter("spawn_viewer", True)
        self.declare_parameter("enable_default_blueprint", True)
        self.declare_parameter("taxel_baseline_samples", 50)
        self.declare_parameter("taxel_smoothing_alpha", 0.35)
        self.declare_parameter("taxel_pressure_valid_min", 100000.0)
        self.declare_parameter("taxel_pressure_invalid_value", 30000.0)
        self.declare_parameter("taxel_pressure_invalid_tolerance", 1000.0)
        self.declare_parameter("taxel_pressure_scale", 10000.0)
        self.declare_parameter("taxel_pressure_deadband", 0.5)
        self.declare_parameter("taxel_pressure_max", 10.0)
        self.declare_parameter("taxel_pressure_gamma", 0.65)
        self.declare_parameter("taxel_visual_spread", 0.45)
        self.declare_parameter("taxel_visual_pad_fill", 0.35)
        self.declare_parameter("raw_pressure_span", 10.0)

        if rr is None:
            raise RuntimeError("rerun-sdk is not installed. Install it with: python3 -m pip install rerun-sdk")

        rr.init("unitree_g1_dex3_diagnostics", spawn=bool(self.get_parameter("spawn_viewer").value))
        self._send_blueprint()

        self._frame = 0
        self._baseline_buffers: dict[str, list[np.ndarray]] = {"left": [], "right": []}
        self._baselines: dict[str, np.ndarray] = {}
        self._smoothed: dict[str, np.ndarray] = {}
        self._counts = {"left": 0, "right": 0}

        self.create_subscription(
            HandState,
            str(self.get_parameter("left_topic").value),
            lambda msg: self._on_hand("left", msg),
            10,
        )
        self.create_subscription(
            HandState,
            str(self.get_parameter("right_topic").value),
            lambda msg: self._on_hand("right", msg),
            10,
        )

        self.get_logger().info("Dex3 Rerun diagnostics started in read-only mode.")

    def _send_blueprint(self) -> None:
        if not bool(self.get_parameter("enable_default_blueprint").value) or rrb is None:
            return

        blueprint = rrb.Blueprint(
            rrb.Vertical(
                rrb.Horizontal(
                    rrb.Grid(
                        rrb.Spatial2DView(
                            name="Left Hand Tactile Raw",
                            origin="g1/dex3/left/tactile_raw_image",
                            contents="$origin",
                        ),
                        rrb.Spatial2DView(
                            name="Right Hand Tactile Raw",
                            origin="g1/dex3/right/tactile_raw_image",
                            contents="$origin",
                        ),
                        grid_columns=1,
                        name="Hand Layouts",
                    ),
                    rrb.Vertical(
                        rrb.Spatial2DView(
                            name="Left Grouped Raw Taxels",
                            origin="g1/dex3/left/grouped_raw_taxels",
                            contents="$origin",
                        ),
                        rrb.Spatial2DView(
                            name="Right Grouped Raw Taxels",
                            origin="g1/dex3/right/grouped_raw_taxels",
                            contents="$origin",
                        ),
                        row_shares=[1, 1],
                        name="Grouped Raw Taxels",
                    ),
                    column_shares=[1, 4],
                ),
                rrb.Grid(
                    rrb.TimeSeriesView(
                        name="Thumb Tactile Raw",
                        origin="g1/dex3/timeseries/thumb",
                        contents="$origin/**",
                    ),
                    rrb.TimeSeriesView(
                        name="Finger 1 Tactile Raw",
                        origin="g1/dex3/timeseries/finger_1",
                        contents="$origin/**",
                    ),
                    rrb.TimeSeriesView(
                        name="Finger 2 Tactile Raw",
                        origin="g1/dex3/timeseries/finger_2",
                        contents="$origin/**",
                    ),
                    rrb.TimeSeriesView(
                        name="Palm Tactile Raw",
                        origin="g1/dex3/timeseries/palm",
                        contents="$origin/**",
                    ),
                    grid_columns=2,
                    name="Tactile Raw Group Trends",
                ),
                row_shares=[3, 2],
            ),
            collapse_panels=False,
        )
        rr.send_blueprint(blueprint)

    def _set_time(self) -> None:
        self._frame += 1
        rr.set_time("dex_frame", sequence=self._frame)

    def _on_hand(self, side: str, msg: HandState) -> None:
        self._set_time()
        self._counts[side] += 1

        raw = self._pressure_matrix(msg)
        processed = self._processed_pressures(side, raw)
        rr.log(f"g1/dex3/{side}/tactile_raw_image", rr.Image(self._render_hand_image(side, processed)))
        rr.log(
            f"g1/dex3/{side}/grouped_raw_taxels",
            rr.Image(self._render_grouped_taxel_matrix(raw, processed)),
        )
        self._log_group_timeseries(side, processed)

        strongest = self._strongest_processed_taxel(processed)
        status = (
            f"{side} samples={self._counts[side]} "
            f"strongest_sensor={strongest[0]} strongest_taxel={strongest[1]} "
            f"value={strongest[2]:.3f}"
        )
        rr.log(f"g1/dex3/{side}/status", rr.TextDocument(status))

        for sensor_id, sensor in enumerate(msg.press_sensor_state):
            pressures = [float(value) for value in sensor.pressure]
            temperatures = [float(value) for value in sensor.temperature]
            root = f"g1/dex3/{side}/raw/s{sensor_id:02d}"
            rr.log(f"{root}/pressure_grid", rr.BarChart(pressures))
            rr.log(f"{root}/temperature_grid", rr.BarChart(temperatures))
            rr.log(f"{root}/lost", rr.Scalars(int(sensor.lost)))

        if self._counts[side] % 100 == 1:
            self.get_logger().info(status)

    def _pressure_matrix(self, msg: HandState) -> np.ndarray:
        rows = []
        for sensor in msg.press_sensor_state:
            rows.append([float(value) for value in sensor.pressure])
        if not rows:
            return np.empty((0, 12), dtype=np.float32)
        return np.asarray(rows, dtype=np.float32)

    def _log_group_timeseries(self, side: str, processed: np.ndarray) -> None:
        if processed.size == 0:
            return
        for group_name, sensor_ids in PAD_GROUPS.items():
            available_ids = [sensor_id for sensor_id in sensor_ids if sensor_id < processed.shape[0]]
            if not available_ids:
                continue
            values = processed[available_ids, :]
            rr.log(f"g1/dex3/timeseries/{group_name}/{side}_max", rr.Scalars(float(np.max(values))))
            rr.log(f"g1/dex3/timeseries/{group_name}/{side}_mean", rr.Scalars(float(np.mean(values))))
            for sensor_id in available_ids:
                rr.log(
                    f"g1/dex3/timeseries/{group_name}/{side}_id{sensor_id}_max",
                    rr.Scalars(float(np.max(processed[sensor_id]))),
                )

    def _processed_pressures(self, side: str, raw: np.ndarray) -> np.ndarray:
        if raw.size == 0:
            return raw

        valid = self._valid_mask(raw)
        baseline = self._baselines.get(side)
        target_samples = int(self.get_parameter("taxel_baseline_samples").value)
        if baseline is None and target_samples > 0:
            buffer = self._baseline_buffers[side]
            buffer.append(np.where(valid, raw, np.nan))
            if len(buffer) >= target_samples:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", category=RuntimeWarning)
                    baseline = np.nanmedian(np.stack(buffer, axis=0), axis=0)
                baseline = np.nan_to_num(
                    baseline,
                    nan=float(self.get_parameter("taxel_pressure_valid_min").value),
                )
                self._baselines[side] = baseline
                self.get_logger().info(f"{side} Dex3 baseline ready samples={len(buffer)}")
            else:
                rr.log(
                    f"g1/dex3/{side}/status",
                    rr.TextDocument(f"collecting baseline {len(buffer)}/{target_samples}"),
                )
                return np.zeros_like(raw, dtype=np.float32)

        if baseline is None:
            baseline = np.zeros_like(raw, dtype=np.float32)

        scale = float(self.get_parameter("taxel_pressure_scale").value)
        if scale <= 0.0:
            scale = 10000.0
        delta = np.where(valid, np.maximum(raw - baseline, 0.0) / scale, 0.0)

        alpha = float(np.clip(float(self.get_parameter("taxel_smoothing_alpha").value), 0.0, 1.0))
        previous = self._smoothed.get(side)
        if previous is not None and previous.shape == delta.shape:
            delta = alpha * delta + (1.0 - alpha) * previous
        self._smoothed[side] = delta

        deadband = float(self.get_parameter("taxel_pressure_deadband").value)
        if deadband > 0.0:
            delta = np.where(delta > deadband, delta - deadband, 0.0)
        return delta

    def _valid_mask(self, raw: np.ndarray) -> np.ndarray:
        valid_min = float(self.get_parameter("taxel_pressure_valid_min").value)
        invalid_value = float(self.get_parameter("taxel_pressure_invalid_value").value)
        invalid_tolerance = float(self.get_parameter("taxel_pressure_invalid_tolerance").value)
        return (
            np.isfinite(raw)
            & (raw >= valid_min)
            & (np.abs(raw - invalid_value) > invalid_tolerance)
        )

    def _render_hand_image(self, side: str, pressure_values: np.ndarray) -> np.ndarray:
        image = np.full((260, 360, 3), [18, 20, 24], dtype=np.uint8)
        outline = np.asarray([72, 78, 88], dtype=np.uint8)
        palm_fill = np.asarray([34, 38, 45], dtype=np.uint8)

        palm_x, palm_y, palm_w, palm_h = 132, 166, 96, 72
        image[palm_y : palm_y + palm_h, palm_x : palm_x + palm_w] = palm_fill
        image[palm_y : palm_y + 2, palm_x : palm_x + palm_w] = outline
        image[palm_y + palm_h - 2 : palm_y + palm_h, palm_x : palm_x + palm_w] = outline
        image[palm_y : palm_y + palm_h, palm_x : palm_x + 2] = outline
        image[palm_y : palm_y + palm_h, palm_x + palm_w - 2 : palm_x + palm_w] = outline

        for sensor_id, x, y, width, height in self._pad_layout(side):
            if sensor_id >= len(pressure_values):
                continue
            self._paste_taxel_pad(image, pressure_values[sensor_id], x, y, (width, height))
        return image

    def _pad_layout(self, side: str) -> list[tuple[int, int, int, int, int]]:
        left_layout = [
            (5, 104, 22, 52, 58),
            (4, 104, 86, 52, 58),
            (3, 204, 22, 52, 58),
            (2, 204, 86, 52, 58),
            (6, 84, 164, 58, 34),
            (7, 150, 164, 58, 34),
            (8, 216, 164, 58, 34),
            (0, 292, 154, 46, 34),
            (1, 292, 198, 46, 34),
        ]
        if side != "right":
            return left_layout
        return [(sensor_id, 360 - x - width, y, width, height) for sensor_id, x, y, width, height in left_layout]

    def _paste_taxel_pad(
        self,
        image: np.ndarray,
        pressures: Iterable[float],
        x: int,
        y: int,
        pad_size: tuple[int, int],
    ) -> None:
        pad = self._render_taxel_pad(pressures, pad_size)
        height, width = pad.shape[:2]
        image[y : y + height, x : x + width] = pad

    def _render_taxel_pad(self, pressures: Iterable[float], pad_size: tuple[int, int]) -> np.ndarray:
        width, height = pad_size
        pad = np.full((height, width, 3), [42, 46, 54], dtype=np.uint8)
        pressure_list = list(pressures)
        values = np.asarray((pressure_list + [0.0] * 12)[:12], dtype=np.float32).reshape((3, 4))
        normalized = self._normalize_processed(values)
        display_values = self._spread_taxels(normalized)
        colors = self._jet_colormap(display_values)

        pad_level = float(np.max(normalized)) if normalized.size else 0.0
        fill_ratio = float(np.clip(float(self.get_parameter("taxel_visual_pad_fill").value), 0.0, 1.0))
        if pad_level > 0.0 and fill_ratio > 0.0:
            fill_color = self._jet_colormap(np.asarray([[pad_level * fill_ratio]], dtype=np.float32))[0, 0]
            pad[:, :] = fill_color

        cell_w = width // 4
        cell_h = height // 3
        for row in range(3):
            for column in range(4):
                x0 = column * cell_w
                y0 = row * cell_h
                x1 = width if column == 3 else (column + 1) * cell_w
                y1 = height if row == 2 else (row + 1) * cell_h
                pad[y0:y1, x0:x1] = colors[row, column]

        grid_color = np.asarray([18, 20, 24], dtype=np.uint8)
        for column in range(1, 4):
            x = column * cell_w
            pad[:, max(0, x - 1) : min(width, x + 1)] = grid_color
        for row in range(1, 3):
            y = row * cell_h
            pad[max(0, y - 1) : min(height, y + 1), :] = grid_color
        return pad

    def _normalize_processed(self, values: np.ndarray) -> np.ndarray:
        configured_max = float(self.get_parameter("taxel_pressure_max").value)
        pressure_max = configured_max if configured_max > 0.0 else float(np.max(values))
        if pressure_max <= 0.0:
            pressure_max = 1.0
        normalized = np.clip(values / pressure_max, 0.0, 1.0)
        gamma = float(self.get_parameter("taxel_pressure_gamma").value)
        if gamma > 0.0:
            normalized = np.power(normalized, gamma)
        return normalized

    def _spread_taxels(self, normalized: np.ndarray) -> np.ndarray:
        spread = float(np.clip(float(self.get_parameter("taxel_visual_spread").value), 0.0, 1.0))
        if spread <= 0.0:
            return normalized

        padded = np.pad(normalized, 1, mode="edge")
        neighbor_max = np.zeros_like(normalized)
        for row_offset in range(3):
            for column_offset in range(3):
                if row_offset == 1 and column_offset == 1:
                    continue
                neighbor_max = np.maximum(
                    neighbor_max,
                    padded[
                        row_offset : row_offset + normalized.shape[0],
                        column_offset : column_offset + normalized.shape[1],
                    ],
                )
        return np.maximum(normalized, neighbor_max * spread)

    def _render_grouped_taxel_matrix(self, raw: np.ndarray, processed: np.ndarray) -> np.ndarray:
        image = np.full((250, 1600, 3), [18, 20, 24], dtype=np.uint8)
        if raw.size == 0:
            return image

        values = self._normalize_raw(raw[:9, :12])
        group_boxes = [
            ("thumb", PAD_GROUPS["thumb"], 26, 34),
            ("finger 1", PAD_GROUPS["finger_1"], 378, 34),
            ("finger 2", PAD_GROUPS["finger_2"], 730, 34),
            ("palm", PAD_GROUPS["palm"], 1082, 34),
        ]
        for group_label, sensor_ids, x, y in group_boxes:
            self._draw_group_box(image, group_label, sensor_ids, values, processed, x, y)
        return image

    def _draw_group_box(
        self,
        image: np.ndarray,
        group_label: str,
        sensor_ids: list[int],
        normalized_raw: np.ndarray,
        processed: np.ndarray,
        x: int,
        y: int,
    ) -> None:
        cell_w = 24
        cell_h = 24
        pad_w = cell_w * 4
        pad_h = cell_h * 3
        pad_gap = 24
        label_color = (210, 214, 222)
        weak_label = (145, 152, 164)
        border = np.asarray([70, 76, 88], dtype=np.uint8)

        box_w = max(324, len(sensor_ids) * (pad_w + pad_gap) + 32)
        box_h = 184
        image[y : y + box_h, x : x + box_w] = [24, 27, 33]
        image[y : y + 2, x : x + box_w] = border
        image[y + box_h - 2 : y + box_h, x : x + box_w] = border
        image[y : y + box_h, x : x + 2] = border
        image[y : y + box_h, x + box_w - 2 : x + box_w] = border

        self._put_text(image, group_label, (x + 14, y + 30), 0.72, label_color)

        for index, sensor_id in enumerate(sensor_ids):
            pad_x = x + 16 + index * (pad_w + pad_gap)
            pad_y = y + 70
            self._put_text(image, f"id {sensor_id}", (pad_x, pad_y - 12), 0.44, weak_label)
            if sensor_id >= normalized_raw.shape[0]:
                continue
            colors = self._jet_colormap(normalized_raw[sensor_id].reshape((3, 4)))
            for row in range(3):
                for column in range(4):
                    x0 = pad_x + column * cell_w
                    y0 = pad_y + row * cell_h
                    image[y0 : y0 + cell_h - 1, x0 : x0 + cell_w - 1] = colors[row, column]

            if processed.size and sensor_id < processed.shape[0]:
                peak = float(np.max(processed[sensor_id]))
                mean = float(np.mean(processed[sensor_id]))
                self._put_text(image, f"max {peak:.2f}", (pad_x, pad_y + pad_h + 28), 0.44, weak_label)
                self._put_text(image, f"avg {mean:.2f}", (pad_x, pad_y + pad_h + 50), 0.44, weak_label)

    def _put_text(
        self,
        image: np.ndarray,
        text: str,
        origin: tuple[int, int],
        scale: float,
        color: tuple[int, int, int],
    ) -> None:
        if cv2 is None:
            return
        cv2.putText(
            image,
            text,
            origin,
            cv2.FONT_HERSHEY_SIMPLEX,
            scale,
            color,
            thickness=1,
            lineType=cv2.LINE_AA,
        )

    def _normalize_raw(self, raw: np.ndarray) -> np.ndarray:
        valid = self._valid_mask(raw)
        scale = float(self.get_parameter("taxel_pressure_scale").value)
        if scale <= 0.0:
            scale = 10000.0
        valid_min = float(self.get_parameter("taxel_pressure_valid_min").value)
        span = float(self.get_parameter("raw_pressure_span").value)
        if span <= 0.0:
            span = 10.0
        scaled = np.where(valid, np.maximum(raw - valid_min, 0.0) / scale, 0.0)
        return np.clip(scaled / span, 0.0, 1.0)

    def _jet_colormap(self, normalized: np.ndarray) -> np.ndarray:
        values = np.asarray(normalized, dtype=np.float32)
        stops = np.asarray(
            [
                [0, 0, 95],
                [0, 80, 255],
                [0, 220, 255],
                [80, 255, 80],
                [255, 230, 0],
                [255, 70, 0],
                [180, 0, 0],
            ],
            dtype=np.float32,
        )
        scaled = np.clip(values, 0.0, 1.0) * (len(stops) - 1)
        lower = np.floor(scaled).astype(np.int32)
        upper = np.clip(lower + 1, 0, len(stops) - 1)
        blend = (scaled - lower)[..., np.newaxis]
        colors = stops[lower] * (1.0 - blend) + stops[upper] * blend
        colors = np.where(values[..., np.newaxis] <= 0.0, [22, 26, 34], colors)
        return np.clip(colors, 0.0, 255.0).astype(np.uint8)

    def _strongest_processed_taxel(self, processed: np.ndarray) -> tuple[int | None, int | None, float]:
        if processed.size == 0:
            return None, None, 0.0
        sensor_scores = np.max(processed, axis=1)
        sensor_id = int(np.argmax(sensor_scores))
        taxel_id = int(np.argmax(processed[sensor_id]))
        return sensor_id, taxel_id, float(processed[sensor_id, taxel_id])


def main() -> None:
    rclpy.init()
    node = DexRerun()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
