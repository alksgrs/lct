import json
from pathlib import Path

import ezdxf

from greenplan.cli import run


def test_real_output_preserves_source_and_is_deterministic(tmp_path):
    project_root = Path(__file__).resolve().parent.parent
    input_path = project_root / "_06_10000176_Генплан_Олимп.dxf"

    out1 = tmp_path / "out1.dxf"
    json1 = tmp_path / "out1.json"

    out2 = tmp_path / "out2.dxf"
    json2 = tmp_path / "out2.json"

    run(
        str(input_path),
        str(out1),
        "tree",
        json_output_path=str(json1)
    )

    run(
        str(input_path),
        str(out2),
        "tree",
        json_output_path=str(json2)
    )

    source = ezdxf.readfile(str(input_path))
    result1 = ezdxf.readfile(str(out1))
    result2 = ezdxf.readfile(str(out2))

    data1 = json.loads(json1.read_text(encoding="utf-8"))
    data2 = json.loads(json2.read_text(encoding="utf-8"))

    assert len(result1.modelspace()) == (
        len(source.modelspace()) + data1["placements_count"]
    )

    assert len(result2.modelspace()) == (
        len(source.modelspace()) + data2["placements_count"]
    )

    source_layers = sorted(
        entity.dxf.layer
        for entity in source.modelspace()
    )

    result_layers = sorted(
        entity.dxf.layer
        for entity in result1.modelspace()
        if entity.dxf.layer != "PLANTING_TREES"
    )

    assert result_layers == source_layers

    points1 = [
        (item["x"], item["y"])
        for item in data1["placements"]
    ]

    points2 = [
        (item["x"], item["y"])
        for item in data2["placements"]
    ]

    assert points1 == points2

