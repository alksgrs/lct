from pathlib import Path

import ezdxf
from shapely.geometry import Point

from greenplan.writer.dxf_writer import write_placements


def test_write_placements():
    project_root = Path(__file__).resolve().parent.parent

    input_path = project_root / "test.dxf"
    output_path = project_root / "test_output.dxf"

    points = [
        Point(10, 10),
        Point(20, 20),
        Point(30, 30)
    ]

    write_placements(
        str(input_path),
        str(output_path),
        points
    )

    assert output_path.exists()

    doc = ezdxf.readfile(output_path)
    modelspace = doc.modelspace()

    planting_points = [
        entity
        for entity in modelspace
        if entity.dxf.layer == "PLANTING_TREES"
    ]

    assert len(planting_points) == 3

    output_path.unlink()