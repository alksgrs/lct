from math import sqrt

from shapely.geometry import Point, Polygon


def create_hex_grid(
    area: Polygon,
    spacing: float
) -> list[Point]:
    if area.is_empty:
        return []

    if spacing <= 0:
        raise ValueError("Spacing must be positive")

    min_x, min_y, max_x, max_y = area.bounds

    horizontal_step = spacing
    vertical_step = spacing * sqrt(3) / 2

    points = []

    row = 0
    y = min_y

    while y <= max_y:
        offset = 0

        if row % 2 == 1:
            offset = horizontal_step / 2

        x = min_x + offset

        while x <= max_x:
            point = Point(x, y)

            if area.contains(point):
                points.append(point)

            x += horizontal_step

        y += vertical_step
        row += 1

    return points