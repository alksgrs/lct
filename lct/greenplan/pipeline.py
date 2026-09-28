from greenplan.constraints.constraints import (
    apply_bin_offset,
    build_allowed_zone
)
from greenplan.parser.dxf_parser import read_dxf
from greenplan.planner.config import load_planting_config
from greenplan.planner.planner import create_plan_with_rejections
from greenplan.rules.loader import load_rules
from greenplan.rules.rule_selector import get_rules


def build_plan(
    input_path: str,
    rules_path: str,
    planting_path: str,
    species_type: str
):
    features = read_dxf(input_path)

    rules = load_rules(rules_path)

    planting_rules = get_rules(
        rules,
        species_type
    )

    allowed_zone = build_allowed_zone(
        features,
        planting_rules
    )

    config = load_planting_config(
        planting_path
    )

    if species_type not in config:
        raise ValueError(
            f"Planting config not found: {species_type}"
        )

    species_config = config[species_type]

    if species_type == "tree":
        bin_offset = species_config.get(
            "bin_offset_m",
            0
        )

        allowed_zone = apply_bin_offset(
            allowed_zone,
            features,
            bin_offset
        )

    placements, rejections = create_plan_with_rejections(
        area=allowed_zone,
        species_type=species_type,
        rules=planting_rules,
        features=features,
        grid_spacing=species_config["grid_spacing_m"],
        min_spacing=species_config["min_spacing_m"]
    )

    return placements, rejections

