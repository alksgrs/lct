from greenplan.constraints.constraints import get_site_boundary
from greenplan.parser.dxf_parser import read_dxf
from greenplan.planner.config import load_planting_config
from greenplan.planner.planner import create_plan_with_rejections
from greenplan.rules.loader import load_rules
from greenplan.rules.rule_selector import get_rules
from greenplan.models import FeatureKind


def build_plan(
    input_path: str,
    rules_path: str,
    planting_path: str,
    species_type: str,
    layers_path: str = "data/config/layers.yaml",
    warnings=None
):
    features = read_dxf(
        input_path,
        layers_path
    )
    if warnings is not None:
        unknown_layers = sorted({
            feature.source_layer
            for feature in features
            if feature.kind == FeatureKind.UNKNOWN
        })

        warnings.extend(
            f"Неизвестный слой: {layer}"
            for layer in unknown_layers
        )

    site_boundary = get_site_boundary(features)
    rules = load_rules(rules_path)
    planting_rules = get_rules(
        rules,
        species_type
    )

    config = load_planting_config(
        planting_path
    )

    if species_type not in config:
        raise ValueError(
            f"Planting config not found: {species_type}"
        )

    species_config = config[species_type]

    bin_offset = 0
    if species_type == "tree":
        bin_offset = species_config.get(
            "bin_offset_m",
            0
        )

    return create_plan_with_rejections(
        area=site_boundary,
        species_type=species_type,
        rules=planting_rules,
        features=features,
        grid_spacing=species_config["grid_spacing_m"],
        min_spacing=species_config["min_spacing_m"],
        bin_offset=bin_offset
    )

