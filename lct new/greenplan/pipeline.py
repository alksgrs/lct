from greenplan.constraints.constraints import get_site_boundary
from greenplan.parser.dxf_parser import parse_dxf
from greenplan.planner.config import load_planting_config
from greenplan.planner.planner import create_plan_with_rejections
from greenplan.rules.loader import load_rules
from greenplan.rules.rule_selector import get_rules


def build_plan(
    input_path: str,
    rules_path: str,
    planting_path: str,
    species_type: str,
    layers_path: str = "data/config/layers.yaml",
    warnings=None,
    unresolved_layers=None,
    overrides=None,
    boundary_layer=None,
    boundary_method=None
):
    parsed = parse_dxf(
        input_path,
        layers_path,
        overrides
    )
    features = parsed.features

    if unresolved_layers is not None:
        unresolved_layers.extend(parsed.unresolved_layers)

    if warnings is not None:
        warnings.extend(
            f"Неизвестный слой: {item['layer']}"
            for item in parsed.unresolved_layers
        )

    site_boundary, detected_boundary_method = get_site_boundary(features, boundary_layer=boundary_layer)
    if boundary_method is not None:
        boundary_method.append(detected_boundary_method)
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

