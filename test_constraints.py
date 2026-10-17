from pathlib import Path

from greenplan.constraints.constraints import build_allowed_zone
from greenplan.models import FeatureKind, Rule
from greenplan.parser.dxf_parser import read_dxf


def test_build_allowed_zone():
    project_root = Path(__file__).resolve().parent.parent
    dxf_path = project_root / "test.dxf"

    features = read_dxf(str(dxf_path))

    rules = [
        Rule(
            id="test_water_tree",
            object=FeatureKind.PIPE_WATER,
            planting="tree",
            min_distance_m=2.0,
            act="TEST",
            clause="TEST",
            verified=True
        ),
        Rule(
            id="test_building_tree",
            object=FeatureKind.BUILDING,
            planting="tree",
            min_distance_m=5.0,
            act="TEST",
            clause="TEST",
            verified=True
        )
    ]

    allowed_zone = build_allowed_zone(
        features,
        rules
    )

    assert not allowed_zone.is_empty
    assert allowed_zone.area < 6000