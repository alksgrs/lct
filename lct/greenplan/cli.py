import argparse

from greenplan.pipeline import build_plan
from greenplan.writer.dxf_writer import write_placements
from greenplan.writer.json_writer import write_placements_json


def run(
    input_path: str,
    output_path: str,
    species_type: str = "tree",
    rules_path: str = "data/rules/sp42.yaml",
    planting_path: str = "data/rules/planting.yaml"
):
    placements, rejections = build_plan(
        input_path=input_path,
        rules_path=rules_path,
        planting_path=planting_path,
        species_type=species_type
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

    json_output_path = str(
        output_path.rsplit(".", 1)[0] + ".json"
    )

    write_placements_json(
        placements=placements,
        output_path=json_output_path,
        input_path=input_path,
        species_type=species_type,
        rejections=rejections
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
            "shrub",
            "groundcover"
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

    args = parser.parse_args()

    run(
        input_path=args.input,
        output_path=args.output,
        species_type=args.species,
        rules_path=args.rules,
        planting_path=args.planting
    )


if __name__ == "__main__":
    main()