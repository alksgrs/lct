import argparse

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
    layers_path="data/config/layers.yaml"
):
    warnings = []

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
        warnings=warnings
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
        warnings
    )

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

    args = parser.parse_args()

    run(
        input_path=args.input,
        rules_path=args.rules,
        planting_path=args.planting,
        species_type=args.species,
        output_path=args.output,
        json_output_path=args.json,
        layers_path=args.layers
    )


if __name__ == "__main__":
    main()