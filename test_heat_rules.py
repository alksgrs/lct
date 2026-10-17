from greenplan.models import FeatureKind
from greenplan.rules.loader import load_rules


def test_heat_rules_can_be_loaded_when_verified(tmp_path):
    rules_file = tmp_path / "rules.yaml"

    rules_file.write_text(
        """
rules:
  - id: heat_tree
    object: PIPE_HEAT
    planting: tree
    min_distance_m: 2.0
    act: "СП 42.13330.2016"
    clause: "таблица 9.1"
    verified: true

  - id: heat_shrub
    object: PIPE_HEAT
    planting: shrub
    min_distance_m: 1.0
    act: "СП 42.13330.2016"
    clause: "таблица 9.1"
    verified: true
""",
        encoding="utf-8"
    )

    rules = load_rules(str(rules_file))

    assert len(rules) == 2
    assert rules[0].object == FeatureKind.PIPE_HEAT
    assert rules[0].min_distance_m == 2.0
    assert rules[1].object == FeatureKind.PIPE_HEAT
    assert rules[1].min_distance_m == 1.0

