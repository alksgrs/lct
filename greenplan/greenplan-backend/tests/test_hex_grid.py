from shapely.geometry import Polygon

from greenplan.planner.hex_grid import create_hex_grid


def test_create_hex_grid():
    area = Polygon([
        (0, 0),
        (20, 0),
        (20, 20),
        (0, 20)
    ])

    points = create_hex_grid(
        area,
        spacing=5.0
    )

    assert len(points) > 0

    for point in points:
        assert area.contains(point)