import pytest
from shapely.geometry import LineString, Point

from greenplan.models import Feature, FeatureKind, RuleKind
from greenplan.planner.feature_index import FeatureIndex
from greenplan.planner.rationale import check_rule
from greenplan.rules.loader import load_pending_rules, load_rules
from greenplan.rules.rule_selector import get_rule, get_rules
from tests.paths import RULES


@pytest.fixture(scope="module")
def rules():
    return load_rules(RULES)


def test_every_enabled_rule_has_source(rules):
    assert rules
    for rule in rules:
        assert rule.act and rule.clause
        assert rule.verified


def test_rule_kinds_are_consistent(rules):
    kinds = {rule.kind for rule in rules}
    assert kinds == {RuleKind.DISTANCE, RuleKind.NOT_REGULATED, RuleKind.BAN}
    for rule in rules:
        if rule.kind == RuleKind.DISTANCE:
            assert rule.min_distance_m > 0
        if rule.kind == RuleKind.BAN:
            assert rule.zone_m > 0
            assert rule.planting == "any"
        if rule.kind == RuleKind.NOT_REGULATED:
            assert rule.min_distance_m is None
            assert rule.limit_m == 0


def test_table_values(rules):
    assert get_rule(rules, FeatureKind.ROAD, "tree").min_distance_m == 2.0
    assert get_rule(rules, FeatureKind.BUILDING, "tree").min_distance_m == 5.0
    assert get_rule(rules, FeatureKind.LIGHTING, "tree").min_distance_m == 4.0
    assert get_rule(rules, FeatureKind.PIPE_GAS, "shrub").kind == RuleKind.NOT_REGULATED
    assert get_rule(rules, FeatureKind.POWERLINE_04KV, "shrub").zone_m == 2.0
    assert get_rule(rules, FeatureKind.POWERLINE_110KV, "tree").zone_m == 20.0
    assert get_rule(rules, FeatureKind.TRAM_TRACK, "shrub").min_distance_m == 3.0
    assert get_rule(rules, FeatureKind.RETAINING_WALL, "tree").min_distance_m == 3.0
    assert get_rule(rules, FeatureKind.SLOPE, "shrub").min_distance_m == 0.5


def test_whole_table_is_loaded(rules):
    ids = {rule.id for rule in rules}
    for row in ("gas", "sewer", "water", "drainage", "heat", "cable", "building", "road", "pavement",
                "lighting", "tram", "retaining_wall", "slope"):
        assert f"{row}_tree" in ids and f"{row}_shrub" in ids
    assert all(rule.source_url for rule in rules)


def test_unverified_rules_are_not_loaded(tmp_path):
    path = tmp_path / "rules.yaml"
    path.write_text(
        "rules:\n"
        "- id: draft\n  object: ROAD\n  planting: tree\n  min_distance_m: 9\n"
        "  act: X\n  clause: Y\n  verified: false\n"
        "- id: ready\n  object: ROAD\n  planting: tree\n  min_distance_m: 2\n"
        "  act: X\n  clause: Y\n  verified: true\n",
        encoding="utf-8",
    )
    assert [rule.id for rule in load_rules(str(path))] == ["ready"]
    assert [rule["rule_id"] for rule in load_pending_rules(str(path))] == ["draft"]


def test_bans_apply_to_every_planting_type(rules):
    for species in ("tree", "shrub"):
        objects = {rule.object for rule in get_rules(rules, species) if rule.kind == RuleKind.BAN}
        assert FeatureKind.POWERLINE_04KV in objects


def test_loader_rejects_rule_without_distance(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        "rules:\n"
        "- id: broken\n  object: ROAD\n  planting: tree\n  kind: distance\n"
        "  act: X\n  clause: Y\n  verified: true\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_rules(str(path))


def test_loader_rejects_rule_without_clause(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        "rules:\n"
        "- id: broken\n  object: ROAD\n  planting: tree\n  min_distance_m: 2\n"
        "  act: X\n  verified: true\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_rules(str(path))


def test_check_statuses(rules):
    line = Feature(geom=LineString([(0, 0), (10, 0)]), kind=FeatureKind.POWERLINE_04KV, source_layer="ВЛ")
    gas = Feature(geom=LineString([(0, 5), (10, 5)]), kind=FeatureKind.PIPE_GAS, source_layer="ГАЗ")
    index = FeatureIndex([line, gas])

    ban = get_rule(rules, FeatureKind.POWERLINE_04KV, "shrub")
    assert check_rule(Point(5, 1), [], ban, index).status == "banned_zone"
    assert check_rule(Point(5, 3), [], ban, index).status == "allowed"

    gas_tree = get_rule(rules, FeatureKind.PIPE_GAS, "tree")
    assert check_rule(Point(5, 4), [], gas_tree, index).status == "violated"
    allowed = check_rule(Point(5, 2.5), [], gas_tree, index)
    assert allowed.status == "allowed"
    assert allowed.margin_m == pytest.approx(1.0)

    gas_shrub = get_rule(rules, FeatureKind.PIPE_GAS, "shrub")
    assert check_rule(Point(5, 4.5), [], gas_shrub, index).status == "not_regulated"

    road = get_rule(rules, FeatureKind.ROAD, "tree")
    assert check_rule(Point(5, 2.5), [], road, index).status == "not_applicable"
