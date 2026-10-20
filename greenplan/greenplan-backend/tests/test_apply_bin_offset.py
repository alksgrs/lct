from shapely.geometry import Point, Polygon

from greenplan.constraints.constraints import apply_bin_offset
from greenplan.models import Feature, FeatureKind


def test_apply_bin_offset():
    allowed_zone = Polygon([
        (0, 0),
        (20, 0),
        (20, 20),
        (0, 20)
    ])

    features = [
        Feature(
            geom=Point(10, 10),
            kind=FeatureKind.BIN,
            source_layer="TEST"
        )
    ]

    result = apply_bin_offset(
        allowed_zone,
        features,
        1.0
    )

    assert result.contains(Point(10, 10)) is False
    assert result.contains(Point(5, 5))

