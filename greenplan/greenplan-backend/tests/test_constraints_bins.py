from shapely.geometry import Point

from greenplan.constraints.constraints import build_forbidden_zone


def test_bin_forbidden_zone():
    bins = [
        Point(10, 10),
        Point(30, 10)
    ]

    zone = build_forbidden_zone(
        bins,
        5.0
    )

    assert zone.contains(Point(10, 10))
    assert zone.contains(Point(30, 10))
    assert not zone.contains(Point(20, 30))

