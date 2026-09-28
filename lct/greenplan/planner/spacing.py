from shapely.geometry import Point


def filter_by_spacing(
    points: list[Point],
    min_distance: float
) -> list[Point]:
    if min_distance <= 0:
        raise ValueError("Minimum distance must be positive")

    selected = []

    for point in points:
        can_place = True

        for selected_point in selected:
            if point.distance(selected_point) < min_distance:
                can_place = False
                break

        if can_place:
            selected.append(point)

    return selected

