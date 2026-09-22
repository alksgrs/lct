from pathlib import Path

from shapely.geometry import Point

from greenplan.writer.dxf_writer import write_placements


def test_write_placements():
    project_root = Path(__file__).resolve().parent.parent

    input_path = project_root / "test.dxf"
    output_path = project_root / "test_output.dxf"

    write_placements(
        str(input_path),
        str(output_path),
        [Point(50, 20)]
    )

    assert output_path.exists()

    output_path.unlink()