from math import sqrt

import numpy as np
import shapely
from shapely.geometry import Point, Polygon

DEFAULT_MAX_CANDIDATES = 150_000
MAX_SCAN_POINTS = 20_000_000


class AreaTooLarge(ValueError):
    pass


def _int(value: float) -> str:
    return f"{value:,.0f}".replace(",", "\u00a0")


def estimate_candidates(area: Polygon, spacing: float) -> int:
    return int(area.area / (spacing * spacing * sqrt(3) / 2))


def create_hex_grid(area: Polygon, spacing: float,
                    max_candidates: int | None = DEFAULT_MAX_CANDIDATES) -> list[Point]:
    if area.is_empty:
        return []
    if spacing <= 0:
        raise ValueError("Spacing must be positive")

    if max_candidates is not None and estimate_candidates(area, spacing) > max_candidates:
        raise AreaTooLarge(
            f"Расчётная область слишком велика: {_int(area.area)} м², "
            f"около {_int(estimate_candidates(area, spacing))} точек при шаге {spacing:g} м."
        )

    xs, ys = hex_grid_xy(area, spacing)
    return [Point(float(x), float(y)) for x, y in zip(xs, ys)]


def hex_grid_xy(area: Polygon, spacing: float):
    if area.is_empty:
        return np.empty(0), np.empty(0)
    min_x, min_y, max_x, max_y = area.bounds
    step_y = spacing * sqrt(3) / 2
    rows = int((max_y - min_y) / step_y) + 1
    cols = int((max_x - min_x) / spacing) + 2
    if rows * cols > MAX_SCAN_POINTS:
        raise AreaTooLarge(
            f"Габарит расчётной области слишком велик: {_int(max_x - min_x)} × {_int(max_y - min_y)} м."
        )

    row_index = np.arange(rows)
    ys = min_y + row_index * step_y
    offsets = np.where(row_index % 2 == 1, spacing / 2, 0.0)
    xs = min_x + offsets[:, None] + np.arange(cols)[None, :] * spacing
    ys = np.broadcast_to(ys[:, None], xs.shape)
    inside_box = xs <= max_x
    xs, ys = xs[inside_box], ys[inside_box]

    shapely.prepare(area)
    mask = shapely.contains_xy(area, xs, ys)
    return xs[mask], ys[mask]
