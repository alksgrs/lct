from pathlib import Path

from greenplan.models import FeatureKind
from greenplan.rules.loader import load_rules


def test_load_rules():
    project_root = Path(__file__).resolve().parent.parent
    rules_path = project_root / "data" / "rules" / "regulations.yaml"

    rules = load_rules(str(rules_path))

    assert len(rules) > 0

    water_tree = next(
        rule
        for rule in rules
        if rule.id == "water_tree"
    )

    assert water_tree.object == FeatureKind.PIPE_WATER
    assert water_tree.planting == "tree"
    assert water_tree.min_distance_m == 2.0
    assert water_tree.verified is True