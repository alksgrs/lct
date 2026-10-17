import argparse

from greenplan.config.overrides import parse_override
from greenplan.pipeline import build_plan
from greenplan.writer.dxf_writer import write_placements
from greenplan.writer.json_writer import write_placements_json


def run(
    input_path,
    output_path,
    species_type="tree",
    rules_path="data/rules/sp42.yaml",
    planting_path="data/rules/planting.yaml",
    json_output_path=None,
    layers_path="data/config/layers.yaml",
    overrides=None,
    boundary_layer=None
):
    warnings = []
    unresolved_layers = []
    boundary_method = []

    if json_output_path is None:
        json_output_path = str(
            output_path.rsplit(".", 1)[0] + ".json"
        )

    placements, rejections = build_plan(
        input_path=input_path,
        rules_path=rules_path,
        planting_path=planting_path,
        species_type=species_type,
        layers_path=layers_path,
        warnings=warnings,
        unresolved_layers=unresolved_layers,
        overrides=overrides,
        boundary_layer=boundary_layer,
        boundary_method=boundary_method
    )

    layer_name = {
        "tree": "PLANTING_TREES",
        "shrub": "PLANTING_SHRUBS",
        "groundcover": "PLANTING_GROUNDCOVER"
    }[species_type]

    points = [
        placement.point
        for placement in placements
    ]

    write_placements(
        input_path=input_path,
        output_path=output_path,
        points=points,
        layer_name=layer_name
    )

    write_placements_json(
        placements,
        json_output_path,
        input_path,
        species_type,
        rejections,
        warnings,
        unresolved_layers,
        boundary_method[0] if boundary_method else None
    )

def _override_arg(text):
    try:
        return parse_override(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error))


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "input",
        help="Input DXF file"
    )

    parser.add_argument(
        "--rules",
        default="data/rules/sp42.yaml"
    )

    parser.add_argument(
        "--planting",
        default="data/rules/planting.yaml"
    )

    parser.add_argument(
        "--species",
        default="tree",
        choices=[
            "tree",
            "shrub"
        ]
    )

    parser.add_argument(
        "--output",
        default="out.dxf"
    )

    parser.add_argument(
        "--json",
        default="out.json"
    )

    parser.add_argument(
        "--layers",
        default="data/config/layers.yaml"
    )

    parser.add_argument(
        "--boundary-layer",
        help="имя слоя, содержащего границу участка"
    )

    parser.add_argument(
        "--override",
        action="append",
        default=[],
        type=_override_arg,
        metavar="СЛОЙ=ТИП",
        help="явно задать тип слоя, например ГП_300_300=ROAD; "
             "можно указывать несколько раз"
    )

    args = parser.parse_args()

    run(
        input_path=args.input,
        rules_path=args.rules,
        planting_path=args.planting,
        species_type=args.species,
        output_path=args.output,
        json_output_path=args.json,
        layers_path=args.layers,
        overrides=dict(args.override),
        boundary_layer=args.boundary_layer
    )


if __name__ == "__main__":
    main()

