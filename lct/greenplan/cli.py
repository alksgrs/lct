import argparse
import json

from greenplan.constraints.constraints import build_allowed_zone
from greenplan.models import FeatureKind, Rule
from greenplan.parser.dxf_parser import read_dxf
from greenplan.planner.planner import create_placement
from greenplan.writer.dxf_writer import write_placements


def run(input_path: str, output_path: str) -> None:
    features = read_dxf(input_path)

    rule = Rule(
        id="test_water_tree",
        object=FeatureKind.PIPE_WATER,
        planting="tree",
        min_distance_m=2.0,
        act="TEST",
        clause="TEST",
        verified=True
    )

    allowed_zone = build_allowed_zone(
        features,
        rule
    )

    placement = create_placement(
        allowed_zone=allowed_zone,
        species_type="tree",
        rule=rule
    )

    write_placements(
        input_path,
        output_path,
        [placement.point]
    )

    rationale = {
        "placements": [
            {
                "x": placement.point.x,
                "y": placement.point.y,
                "species_type": placement.species_type,
                "species": placement.species,
                "rules": [
                    {
                        "id": item.id,
                        "object": item.object.value,
                        "planting": item.planting,
                        "min_distance_m": item.min_distance_m,
                        "act": item.act,
                        "clause": item.clause,
                        "verified": item.verified
                    }
                    for item in placement.rationale
                ]
            }
        ]
    }

    json_path = output_path.rsplit(".", 1)[0] + ".json"

    with open(json_path, "w", encoding="utf-8") as file:
        json.dump(
            rationale,
            file,
            ensure_ascii=False,
            indent=4
        )


def main():
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(
        dest="command",
        required=True
    )

    run_parser = subparsers.add_parser("run")

    run_parser.add_argument(
        "--input",
        required=True
    )

    run_parser.add_argument(
        "--output",
        required=True
    )

    args = parser.parse_args()

    if args.command == "run":
        run(
            args.input,
            args.output
        )


if __name__ == "__main__":
    main()