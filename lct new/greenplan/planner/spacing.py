from shapely.geometry import Point
from shapely.strtree import STRtree


def filter_by_spacing(points: list[Point], min_distance: float) -> list[Point]:
    if min_distance <= 0:
        raise ValueError("Minimum distance must be positive")

    selected = []
    recent = []
    tree = None
    indexed_count = 0
    rebuild_every = 128

    for point in points:
        can_place = True
        if tree is not None:
            candidates = tree.query(point.buffer(min_distance))
            for candidate_index in candidates:
                candidate = selected[int(candidate_index)]
                if point.distance(candidate) < min_distance:
                    can_place = False
                    break
        if can_place:
            for selected_point in recent:
                if point.distance(selected_point) < min_distance:
                    can_place = False
                    break
        if can_place:
            selected.append(point)
            recent.append(point)
            if len(recent) >= rebuild_every:
                tree = STRtree(selected)
                recent = []
                indexed_count = len(selected)
    return selected
