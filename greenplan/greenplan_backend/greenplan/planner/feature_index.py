from collections import defaultdict

import numpy as np
import shapely
from shapely.strtree import STRtree

from greenplan.models import Feature, FeatureKind


class FeatureIndex:
    def __init__(self, features: list[Feature]):
        grouped = defaultdict(list)
        for feature in features:
            if feature.geom is not None and not feature.geom.is_empty:
                grouped[feature.kind].append(feature.geom)
        self._geometries = dict(grouped)
        self._trees = {kind: STRtree(geoms) for kind, geoms in grouped.items()}

    def has(self, kind: FeatureKind) -> bool:
        return kind in self._trees

    def nearest(self, point, kind: FeatureKind):
        tree = self._trees.get(kind)
        if tree is None:
            return None
        found = tree.query_nearest(point, all_matches=False)
        return self._geometries[kind][int(found[0])] if len(found) else None

    def nearest_distance(self, point, kind: FeatureKind) -> float | None:
        tree = self._trees.get(kind)
        if tree is None:
            return None
        _, distances = tree.query_nearest(point, return_distance=True, all_matches=False)
        return float(distances[0]) if len(distances) else None

    def within(self, point, kind: FeatureKind, distance: float) -> bool:
        tree = self._trees.get(kind)
        if tree is None:
            return False
        return len(tree.query(point, predicate="dwithin", distance=distance)) > 0

    def contains(self, point, kind: FeatureKind) -> bool:
        tree = self._trees.get(kind)
        if tree is None:
            return False
        return len(tree.query(point, predicate="within")) > 0

    def geometries(self, kind: FeatureKind) -> list:
        return list(self._geometries.get(kind, []))

    def mask_within(self, xs, ys, kind: FeatureKind, distance: float) -> np.ndarray:
        result = np.zeros(len(xs), dtype=bool)
        tree = self._trees.get(kind)
        if tree is None or len(xs) == 0:
            return result
        points = shapely.points(np.asarray(xs), np.asarray(ys))
        if distance > 0:
            hits = tree.query(points, predicate="dwithin", distance=distance)
        else:
            hits = tree.query(points, predicate="intersects")
        result[np.unique(hits[0])] = True
        return result
