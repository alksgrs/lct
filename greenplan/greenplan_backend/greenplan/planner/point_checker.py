from shapely.geometry import Point
from shapely.strtree import STRtree

from greenplan.models import Feature, FeatureKind, Rejection, Rule, RuleKind
from greenplan.planner.feature_index import FeatureIndex


def _ordered(rules: list[Rule]) -> list[Rule]:
    return sorted((r for r in rules if r.kind != RuleKind.NOT_REGULATED),
                  key=lambda r: (r.kind != RuleKind.BAN, -r.limit_m))


def find_violation_detail(point: Point, rules: list[Rule], index: FeatureIndex):
    for rule in _ordered(rules):
        if not index.within(point, rule.object, rule.limit_m):
            continue
        distance = index.nearest_distance(point, rule.object)
        if distance is not None and distance < rule.limit_m:
            return rule, distance
    return None, None


def find_violation(point: Point, features: list[Feature], rules: list[Rule],
                   index: FeatureIndex | None = None) -> Rule | None:
    if not rules or not features and index is None:
        return None
    rule, _ = find_violation_detail(point, rules, index or FeatureIndex(features))
    return rule


def find_bin_violation(point, features, offset, tree=None, bins=None):
    if offset <= 0:
        return False
    bins = bins if bins is not None else [f for f in features if f.kind == FeatureKind.BIN]
    if not bins:
        return False
    geometries = [f.geom for f in bins]
    tree = tree if tree is not None else STRtree(geometries)
    return len(tree.query(point, predicate="dwithin", distance=offset)) > 0


def create_rejection(point, species_type, features, rules):
    rule, distance = find_violation_detail(point, rules, FeatureIndex(features))
    if rule is None:
        return None
    return Rejection(point=point, species_type=species_type, violated=rule, distance_m=distance)
