from shapely.geometry import Point, Polygon

from greenplan.models import Feature, FeatureKind
from greenplan.planner.planner import create_plan_with_rejections


def test_planner_applies_bin_offset():
    features = [
        Feature(
            geom=Polygon([
                (0, 0),
                (20, 0),
                (20, 20),
                (0, 20)
            ]),
            kind=FeatureKind.SITE_BOUNDARY,
            source_layer="TEST"
        ),
        Feature(
            geom=Point(10, 10),
            kind=FeatureKind.BIN,
            source_layer="TEST"
        )
    ]

    placements, rejections = create_plan_with_rejections(
        area=features[0].geom,
        species_type="tree",
        rules=[],
        features=features,
        grid_spacing=5.0,
        min_spacing=1.0,
        bin_offset=0.1
    )

    for placement in placements:
        assert placement.point.distance(Point(10, 10)) >= 0.1