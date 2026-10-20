from tests.paths import GENPLAN
import ezdxf

from ezdxf.disassemble import recursive_decompose
from shapely.geometry import Polygon
from shapely.ops import unary_union


def test_maf_geometry_size():
    doc = ezdxf.readfile(
        GENPLAN
    )

    modelspace = doc.modelspace()

    mafs = [
        entity
        for entity in modelspace
        if entity.dxftype() == "INSERT"
        and entity.dxf.name == "*U476"
        and entity.dxf.layer == "ДВ_ГП_П_МАФ"
    ]

    assert len(mafs) == 119

    for entity in mafs:
        geometries = []

        for item in recursive_decompose([entity]):
            if item.dxftype() != "LWPOLYLINE":
                continue

            if not item.closed:
                continue

            points = [
                (point[0], point[1])
                for point in item.get_points()
            ]

            if len(points) < 3:
                continue

            polygon = Polygon(points)

            if polygon.is_valid and polygon.area > 0:
                geometries.append(polygon)

        geometry = unary_union(geometries)

        assert geometry.is_valid
        assert geometry.area > 0
        assert geometry.area < 2

