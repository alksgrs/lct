from shapely.geometry import LineString, Polygon

from greenplan.models import Feature, FeatureKind, Rule
from greenplan.planner.planner import create_plan_with_rejections


def test_create_plan_with_rejections():
    area = Polygon([
        (0, 0),
        (20, 0),
        (20, 20),
        (0, 20)
    ])

    feature = Feature(
        geom=LineString([
            (10, 0),
            (10, 20)
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

    placements, rejections = create_plan_with_rejections(
        area=area,
        species_type="tree",
        rules=[rule],
        features=[feature],
        grid_spacing=2.0,
        min_spacing=4.0
    )

    assert len(placements) > 0
    assert len(rejections) > 0

    for rejection in rejections:
        assert rejection.species_type == "tree"
        assert rejection.violated == rule