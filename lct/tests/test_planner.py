from pathlib import Path

from greenplan.constraints.constraints import build_allowed_zone
from greenplan.models import FeatureKind, Rule
from greenplan.parser.dxf_parser import read_dxf
from greenplan.planner.planner import create_placement


def test_create_placement():
    project_root = Path(__file__).resolve().parent.parent
    dxf_path = project_root / "test.dxf"

    features = read_dxf(str(dxf_path))

    rule = Rule(
        id="test_water_tree",
        object=FeatureKind.PIPE_WATER,
        planting="tree",
        min_distance_m=2.0,
        act="TEST",
        clause="TEST",
        verified=True
    )

    allowed_zone = build_allowed_zone(features, rule)

    placement = create_placement(
        allowed_zone=allowed_zone,
        species_type="tree",
        rule=rule
    )

    assert placement.point is not None
    assert allowed_zone.contains(placement.point)
    assert placement.species_type == "tree"
    assert placement.species is None
    assert len(placement.rationale) == 1
    assert placement.rationale[0].id == "test_water_tree"

