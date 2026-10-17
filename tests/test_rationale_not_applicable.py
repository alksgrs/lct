from shapely.geometry import Point

from greenplan.models import FeatureKind, Rule
from greenplan.planner.rationale import check_rule


def test_check_rule_not_applicable():
    rule = Rule(
        id="water_tree",
        object=FeatureKind.PIPE_WATER,
        planting="tree",
        min_distance_m=2.0,
        act="SP 42.13330.2016",
        clause="table 9.1",
        verified=True
    )

    result = check_rule(
        Point(10, 10),
        [],
        rule
    )

    assert result.status == "not_applicable"
    assert result.distance_m is None
    assert result.message == (
        "Объектов типа PIPE_WATER в чертеже не найдено"
    )

