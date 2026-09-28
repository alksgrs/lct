from greenplan.models import FeatureKind, Rule


def get_rule(
    rules: list[Rule],
    object_kind: FeatureKind,
    planting: str
) -> Rule:
    for rule in rules:
        if (
            rule.object == object_kind
            and rule.planting == planting
        ):
            return rule

    raise ValueError(
        f"Rule not found: {object_kind.value}, {planting}"
    )


def get_rules(
    rules: list[Rule],
    planting: str
) -> list[Rule]:
    return [
        rule
        for rule in rules
        if rule.planting == planting
    ]

