from shapely.geometry import Point

from greenplan.models import Feature, Rule
from greenplan.models import Feature, Rejection, Rule
from greenplan.models import FeatureKind


def find_bin_violation(point, features, offset):
    if offset <= 0:
        return False

    for feature in features:
        if feature.kind != FeatureKind.BIN:
            continue

        if point.distance(feature.geom) < offset:
            return True

    return False

def find_violation(
    point: Point,
    features: list[Feature],
    rules: list[Rule]
) -> Rule | None:
    for rule in rules:
        matching_features = [
            feature
            for feature in features
            if feature.kind == rule.object
        ]

        for feature in matching_features:
            distance = point.distance(feature.geom)

            if distance < rule.min_distance_m:
                return rule

    return None


def create_rejection(
    point: Point,
    species_type: str,
    features: list[Feature],
    rules: list[Rule]
) -> Rejection | None:
    violated_rule = find_violation(
        point,
        features,
        rules
    )

    if violated_rule is None:
        return None

    return Rejection(
        point=point,
        species_type=species_type,
        violated=violated_rule
    )

