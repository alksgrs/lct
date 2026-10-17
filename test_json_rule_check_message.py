import json

from shapely.geometry import Point

from greenplan.models import Placement, Rule, RuleCheck, FeatureKind
from greenplan.writer.json_writer import write_placements_json


def test_json_contains_rule_check_message(tmp_path):
    rule = Rule(
        id="water_tree",
        object=FeatureKind.PIPE_WATER,
        planting="tree",
        min_distance_m=2.0,
        act="SP 42.13330.2016",
        clause="table 9.1",
        verified=True
    )

    placement = Placement(
        point=Point(10, 10),
        species_type="tree",
        species=None,
        rationale=[],
        rule_checks=[
            RuleCheck(
                rule=rule,
                status="not_applicable",
                distance_m=None,
                message="Объектов типа PIPE_WATER в чертеже не найдено"
            )
        ]
    )

    output_path = tmp_path / "test.json"

    write_placements_json(
        placements=[placement],
        output_path=str(output_path),
        input_path="test.dxf",
        species_type="tree"
    )

    with open(output_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    check = data["placements"][0]["rule_checks"][0]

    assert check["status"] == "not_applicable"
    assert check["distance_m"] is None
    assert check["message"] == (
        "Объектов типа PIPE_WATER в чертеже не найдено"
    )


def test_json_contains_not_applicable_rules(tmp_path):
    rule = Rule(
        id="water_tree",
        object=FeatureKind.PIPE_WATER,
        planting="tree",
        min_distance_m=2.0,
        act="SP 42.13330.2016",
        clause="table 9.1",
        verified=True
    )

    placement = Placement(
        point=Point(10, 10),
        species_type="tree",
        species=None,
        rationale=[],
        rule_checks=[
            RuleCheck(
                rule=rule,
                status="not_applicable",
                distance_m=None,
                message="Объектов типа PIPE_WATER в чертеже не найдено"
            )
        ]
    )

    output_path = tmp_path / "test.json"

    write_placements_json(
        placements=[placement],
        output_path=str(output_path),
        input_path="test.dxf",
        species_type="tree"
    )

    with open(output_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    assert data["not_applicable_rules"] == [
        {
            "rule_id": "water_tree",
            "object": "PIPE_WATER",
            "planting": "tree",
            "message": "Объектов типа PIPE_WATER в чертеже не найдено"
        }
    ]

