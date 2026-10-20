from shapely.geometry import Point

from greenplan.planner.spacing import filter_by_spacing


def test_filter_by_spacing():
    points = [
        Point(0, 0),
        Point(3, 0),
        Point(10, 0),
        Point(20, 0)
    ]

    result = filter_by_spacing(
        points,
        min_distance=5.0
    )

    assert len(result) == 3
    assert result[0] == Point(0, 0)
    assert result[1] == Point(10, 0)
    assert result[2] == Point(20, 0)


def test_all_points_have_required_spacing():
    points = [
        Point(0, 0),
        Point(5, 0),
        Point(10, 0),
        Point(15, 0),
        Point(20, 0)
    ]

    result = filter_by_spacing(
        points,
        min_distance=10.0
    )

    for i in range(len(result)):
        for j in range(i + 1, len(result)):
            assert result[i].distance(result[j]) >= 10.0