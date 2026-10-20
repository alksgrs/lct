from shapely.geometry import Point

from greenplan.constraints.constraints import build_forbidden_zone


def test_bin_offset_from_config():
    bins = [
        Point(10, 10)
    ]

    zone = build_forbidden_zone(
        bins,
        0.1
    )

    assert zone.contains(Point(10, 10))
    assert zone.contains(Point(10.05, 10))
    assert not zone.contains(Point(10.2, 10))

