from pathlib import Path
import json
import ezdxf

from greenplan.cli import run


def test_output_contains_planting_points(tmp_path):
    project_root = Path(__file__).resolve().parent.parent

    input_path = project_root / "test.dxf"
    output_path = tmp_path / "test_output_cli.dxf"

    run(
        str(input_path),
        str(output_path)
    )

    assert output_path.exists()

    doc = ezdxf.readfile(output_path)
    modelspace = doc.modelspace()

    planting_points = [
        entity
        for entity in modelspace
        if entity.dxf.layer == "PLANTING_TREES"
    ]

    assert len(planting_points) > 0

    output_path.unlink()
    json_path = output_path.with_suffix(".json")

    assert json_path.exists()

    with open(
            json_path,
            "r",
            encoding="utf-8"
    ) as file:
        data = json.load(file)

    assert "placements" in data
    assert len(data["placements"]) > 0

    placement = data["placements"][0]

    assert "x" in placement
    assert "y" in placement
    assert "species_type" in placement
    assert "rationale" in placement


def test_output_for_all_species_types(tmp_path):
    project_root = Path(__file__).resolve().parent.parent

    input_path = project_root / "test.dxf"

    species_types = [
        ("tree", "PLANTING_TREES"),
        ("shrub", "PLANTING_SHRUBS"),
    ]

    for species_type, layer_name in species_types:
        output_path = tmp_path / f"{species_type}.dxf"

        run(
            str(input_path),
            str(output_path),
            species_type
        )

        assert output_path.exists()

        doc = ezdxf.readfile(output_path)
        modelspace = doc.modelspace()

        planting_points = [
            entity
            for entity in modelspace
            if entity.dxf.layer == layer_name
        ]

        assert len(planting_points) > 0

        json_path = output_path.with_suffix(".json")

        assert json_path.exists()

        with open(
            json_path,
            "r",
            encoding="utf-8"
        ) as file:
            data = json.load(file)

        assert data["species_type"] == species_type
        assert data["placements_count"] == len(planting_points)
        assert len(data["placements"]) == len(planting_points)