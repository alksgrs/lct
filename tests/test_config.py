from pathlib import Path

from greenplan.planner.config import load_planting_config


def test_load_planting_config():
    project_root = Path(__file__).resolve().parent.parent

    config_path = (
        project_root
        / "data"
        / "rules"
        / "planting.yaml"
    )

    config = load_planting_config(
        str(config_path)
    )

    assert config["tree"]["grid_spacing_m"] == 5.0
    assert config["tree"]["min_spacing_m"] == 10.0

    assert config["shrub"]["grid_spacing_m"] == 2.0
    assert config["shrub"]["min_spacing_m"] == 3.0

    assert config["groundcover"]["grid_spacing_m"] == 1.0
    assert config["groundcover"]["min_spacing_m"] == 1.5


def test_tree_bin_offset():
    config = load_planting_config(
        r"data/rules/planting.yaml"
    )

    assert config["tree"]["bin_offset_m"] == 0.1

