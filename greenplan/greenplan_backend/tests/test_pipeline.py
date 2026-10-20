from pathlib import Path

from greenplan.pipeline import build_plan


BASE_DIR = Path(__file__).resolve().parent.parent

DXF_PATH = BASE_DIR / "test.dxf"
RULES_PATH = BASE_DIR / "data" / "rules" / "regulations.yaml"
PLANTING_PATH = BASE_DIR / "data" / "rules" / "planting.yaml"


def test_build_tree_plan():
    placements, rejections = build_plan(
        input_path=str(DXF_PATH),
        rules_path=str(RULES_PATH),
        planting_path=str(PLANTING_PATH),
        species_type="tree"
    )

    assert isinstance(placements, list)
    assert isinstance(rejections, list)

    for placement in placements:
        assert placement.species_type == "tree"

    for rejection in rejections:
        assert rejection.species_type == "tree"

