from pathlib import Path

from greenplan.models import FeatureKind
from greenplan.rules.loader import load_rules
from greenplan.rules.rule_selector import get_rule, get_rules


def test_get_rule():
    project_root = Path(__file__).resolve().parent.parent
    rules_path = project_root / "data" / "rules" / "regulations.yaml"

    rules = load_rules(str(rules_path))

    rule = get_rule(
        rules,
        FeatureKind.PIPE_WATER,
        "tree"
    )

    assert rule.id == "water_tree"
    assert rule.min_distance_m == 2.0


def test_get_rules():
    project_root = Path(__file__).resolve().parent.parent
    rules_path = project_root / "data" / "rules" / "regulations.yaml"

    rules = load_rules(str(rules_path))

    tree_rules = get_rules(
        rules,
        "tree"
    )

    rule_ids = {rule.id for rule in tree_rules}

    assert "water_tree" in rule_ids
    assert "building_tree" in rule_ids