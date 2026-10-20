import json

from shapely.geometry import Point

from greenplan.models import Rejection

from greenplan.models import (
    FeatureKind,
    Placement,
    Rule
)
from greenplan.writer.json_writer import (
    write_placements_json
)


def test_write_placements_json(tmp_path):
    rule = Rule(
        id="test_water_tree",
        object=FeatureKind.PIPE_WATER,
        planting="tree",
        min_distance_m=2.0,
        act="TEST ACT",
        clause="TEST CLAUSE",
        verified=True
    )

    placement = Placement(
        point=Point(10, 20),
        species_type="tree",
        species=None,
        rationale=[rule]
    )

    output_path = tmp_path / "placements.json"

    write_placements_json(
        [placement],
        str(output_path),
        "test.dxf",
        "tree"
    )

    with open(
        output_path,
        "r",
        encoding="utf-8"
    ) as file:
        data = json.load(file)

    assert data["input"] == "test.dxf"
    assert data["species_type"] == "tree"
    assert data["placements_count"] == 1
    assert len(data["rules"]) == 1
    assert data["rules"][0]["rule_id"] == "test_water_tree"
    assert data["rules"][0]["act"] == "TEST ACT"
    assert data["rules"][0]["clause"] == "TEST CLAUSE"

    assert len(data["placements"]) == 1

    placement_data = data["placements"][0]

    assert placement_data["x"] == 10
    assert placement_data["y"] == 20
    assert placement_data["species_type"] == "tree"

    assert len(placement_data["rationale"]) == 1
    assert placement_data["rationale"][0]["rule_id"] == "test_water_tree"
    assert placement_data["rationale"][0]["act"] == "TEST ACT"
    assert placement_data["rationale"][0]["clause"] == "TEST CLAUSE"


def test_write_rejections_json(tmp_path):
    rule = Rule(
        id="test_water_tree",
        object=FeatureKind.PIPE_WATER,
        planting="tree",
        min_distance_m=2.0,
        act="test act",
        clause="test clause",
        verified=True
    )

    rejection = Rejection(
        point=Point(5, 5),
        species_type="tree",
        violated=rule
    )

    output_path = tmp_path / "result.json"

    write_placements_json(
        [],
        str(output_path),
        "test.dxf",
        "tree",
        rejections=[rejection]
    )

    with open(
        output_path,
        "r",
        encoding="utf-8"
    ) as file:
        data = json.load(file)

    assert data["rejections_count"] == 1
    assert len(data["rejections"]) == 1

    rejection_data = data["rejections"][0]

    assert rejection_data["x"] == 5
    assert rejection_data["y"] == 5
    assert rejection_data["species_type"] == "tree"
    assert rejection_data["violated"]["rule_id"] == "test_water_tree"


