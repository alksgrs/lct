from shapely.geometry import LineString, Point

from greenplan.models import Feature, FeatureKind, Rule
from greenplan.planner.point_checker import find_violation


def test_find_violation():
    feature = Feature(
        geom=LineString([
            (0, 0),
            (10, 0)
        ]),
        kind=FeatureKind.PIPE_WATER,
        source_layer="PIPE_WATER"
    )

    rule = Rule(
        id="water_tree",
        object=FeatureKind.PIPE_WATER,
        planting="tree",
        min_distance_m=2.0,
        act="test",
        clause="test",
        verified=True
    )

    point = Point(5, 1)

    result = find_violation(
        point,
        [feature],
        [rule]
    )

    assert result == rule


def test_no_violation():
    feature = Feature(
        geom=LineString([
            (0, 0),
            (10, 0)
        ]),
        kind=FeatureKind.PIPE_WATER,
        source_layer="PIPE_WATER"
    )

    rule = Rule(
        id="water_tree",
        object=FeatureKind.PIPE_WATER,
        planting="tree",
        min_distance_m=2.0,
        act="test",
        clause="test",
        verified=True
    )

    point = Point(5, 5)

    result = find_violation(
        point,
        [feature],
        [rule]
    )

    assert result is None