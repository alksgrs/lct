from shapely.geometry import Point
from shapely.strtree import STRtree

from greenplan.models import Feature, Rejection, Rule, FeatureKind


def find_bin_violation(point, features, offset, tree=None, bins=None):
    if offset <= 0:
        return False
    bins = bins if bins is not None else [feature for feature in features if feature.kind == FeatureKind.BIN]
    if not bins:
        return False
    geometries = [feature.geom for feature in bins]
    tree = tree if tree is not None else STRtree(geometries)
    for index in sorted(int(i) for i in tree.query(point.buffer(offset))):
        if point.distance(geometries[index]) < offset:
            return True
    return False


def find_violation(point: Point, features: list[Feature], rules: list[Rule], tree=None, feature_geometries=None) -> Rule | None:
    if not rules or not features:
        return None
    geometries = feature_geometries or [feature.geom for feature in features]
    if tree is None:
        tree = STRtree(geometries)
    max_distance = max(rule.min_distance_m for rule in rules)
    queried = tree.query(point.buffer(max_distance))
    candidate_indexes = sorted(int(index) for index in queried)
    for rule in rules:
        for index in candidate_indexes:
            feature = features[index]
            if feature.kind != rule.object:
                continue
            if point.distance(geometries[index]) < rule.min_distance_m:
                return rule
    return None


def create_rejection(point, species_type, features, rules):
    violated_rule = find_violation(point, features, rules)
    if violated_rule is None:
        return None
    return Rejection(point=point, species_type=species_type, violated=violated_rule)
