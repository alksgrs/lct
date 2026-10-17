from shapely.geometry import LineString, Point

from greenplan.models import Feature, FeatureKind, Rule
from greenplan.planner.rationale import check_rule


def test_water_tree_distance():
    feature = Feature(
        geom=LineString([(0, 0), (0, 10)]),
        kind=FeatureKind.PIPE_WATER,
        source_layer="TEST"
    )

    rule = Rule(
        id="water_tree",
        object=FeatureKind.PIPE_WATER,
        planting="tree",
        min_distance_m=2.0,
        act="СП 42.13330.2016",
        clause="таблица 9.1",
        verified=True
    )

    assert check_rule(
        Point(1.9, 5),
        [feature],
        rule
    ).status == "violated"

    assert check_rule(
        Point(2.1, 5),
        [feature],
        rule
    ).status == "allowed"


def test_heat_tree_distance():
    feature = Feature(
        geom=LineString([(0, 0), (0, 10)]),
        kind=FeatureKind.PIPE_HEAT,
        source_layer="TEST"
    )

    rule = Rule(
        id="heat_tree",
        object=FeatureKind.PIPE_HEAT,
        planting="tree",
        min_distance_m=2.0,
        act="СП 42.13330.2016",
        clause="таблица 9.1",
        verified=True
    )

    assert check_rule(
        Point(1.9, 5),
        [feature],
        rule
    ).status == "violated"

    assert check_rule(
        Point(2.1, 5),
        [feature],
        rule
    ).status == "allowed"


def test_heat_shrub_distance():
    feature = Feature(
        geom=LineString([(0, 0), (0, 10)]),
        kind=FeatureKind.PIPE_HEAT,
        source_layer="TEST"
    )

    rule = Rule(
        id="heat_shrub",
        object=FeatureKind.PIPE_HEAT,
        planting="shrub",
        min_distance_m=1.0,
        act="СП 42.13330.2016",
        clause="таблица 9.1",
        verified=True
    )

    assert check_rule(
        Point(0.9, 5),
        [feature],
        rule
    ).status == "violated"

    assert check_rule(
        Point(1.1, 5),
        [feature],
        rule
    ).status == "allowed"


def test_building_tree_distance():
    feature = Feature(
        geom=LineString([(0, 0), (0, 10)]),
        kind=FeatureKind.BUILDING,
        source_layer="TEST"
    )

    rule = Rule(
        id="building_tree",
        object=FeatureKind.BUILDING,
        planting="tree",
        min_distance_m=5.0,
        act="СП 42.13330.2016",
        clause="таблица 9.1",
        verified=True
    )

    assert check_rule(
        Point(4.9, 5),
        [feature],
        rule
    ).status == "violated"

    assert check_rule(
        Point(5.1, 5),
        [feature],
        rule
    ).status == "allowed"


def test_building_shrub_distance():
    feature = Feature(
        geom=LineString([(0, 0), (0, 10)]),
        kind=FeatureKind.BUILDING,
        source_layer="TEST"
    )

    rule = Rule(
        id="building_shrub",
        object=FeatureKind.BUILDING,
        planting="shrub",
        min_distance_m=1.5,
        act="СП 42.13330.2016",
        clause="таблица 9.1",
        verified=True
    )

    assert check_rule(
        Point(1.4, 5),
        [feature],
        rule
    ).status == "violated"

    assert check_rule(
        Point(1.6, 5),
        [feature],
        rule
    ).status == "allowed"

