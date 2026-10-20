from math import floor

from shapely.geometry import Point


def filter_by_spacing(points: list[Point], min_distance: float) -> list[Point]:
    if min_distance <= 0:
        raise ValueError("Minimum distance must be positive")

    cells: dict[tuple[int, int], list[Point]] = {}
    selected = []
    limit = min_distance * min_distance

    for point in points:
        cx, cy = floor(point.x / min_distance), floor(point.y / min_distance)
        blocked = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for other in cells.get((cx + dx, cy + dy), ()):
                    if (point.x - other.x) ** 2 + (point.y - other.y) ** 2 < limit:
                        blocked = True
                        break
                if blocked:
                    break
            if blocked:
                break
        if not blocked:
            selected.append(point)
            cells.setdefault((cx, cy), []).append(point)

    return selected
