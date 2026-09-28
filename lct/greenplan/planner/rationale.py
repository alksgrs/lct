from shapely.geometry import Point

from greenplan.models import (
    Feature,
    Rule,
    RuleCheck
)


def check_rule(
    point: Point,
    features: list[Feature],
    rule: Rule
) -> RuleCheck:
    matching_features = [
        feature
        for feature in features
        if feature.kind == rule.object
    ]

    if not matching_features:
        return RuleCheck(
            rule=rule,
            status="allowed",
            distance_m=None
        )

    distance = min(
        point.distance(feature.geom)
        for feature in matching_features
    )

    status = "allowed"

    if distance < rule.min_distance_m:
        status = "violated"

    return RuleCheck(
        rule=rule,
        status=status,
        distance_m=distance
    )

