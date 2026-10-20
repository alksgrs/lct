from shapely.geometry import Point

from greenplan.models import Feature, Rule, RuleCheck, RuleKind
from greenplan.planner.feature_index import FeatureIndex


def check_rule(point: Point, features: list[Feature], rule: Rule,
               index: FeatureIndex | None = None) -> RuleCheck:
    index = index or FeatureIndex(features)

    if not index.has(rule.object):
        return RuleCheck(rule=rule, status="not_applicable", distance_m=None,
                         message=f"Объектов типа {rule.object.value} в чертеже не найдено")

    distance = index.nearest_distance(point, rule.object)

    if rule.kind == RuleKind.NOT_REGULATED:
        return RuleCheck(rule=rule, status="not_regulated", distance_m=distance,
                         message=rule.note or "Расстояние не нормируется")

    if rule.kind == RuleKind.BAN:
        if distance is not None and distance < rule.limit_m:
            return RuleCheck(rule=rule, status="banned_zone", distance_m=distance, message=rule.note)
        return RuleCheck(rule=rule, status="allowed", distance_m=distance)

    status = "violated" if distance is not None and distance < rule.limit_m else "allowed"
    return RuleCheck(rule=rule, status=status, distance_m=distance)


def check_point(point: Point, rules: list[Rule], index: FeatureIndex) -> list[RuleCheck]:
    return [check_rule(point, [], rule, index) for rule in rules]
