from pathlib import Path
from shapely.geometry import Point


from greenplan.constraints.constraints import build_allowed_zone
from greenplan.models import FeatureKind, Rule
from greenplan.parser.dxf_parser import read_dxf
from greenplan.planner.planner import create_placement, create_placements
from greenplan.models import RuleCheck
from greenplan.planner.rationale import check_rule


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

    rules = [rule]

    allowed_zone = build_allowed_zone(
        features,
        rules
    )

    placement = create_placement(
        allowed_zone=allowed_zone,
        species_type="tree",
        rules=rules
    )

    assert placement.point is not None
    assert allowed_zone.contains(placement.point)
    assert placement.species_type == "tree"
    assert placement.species is None
    assert len(placement.rationale) == 1
    assert placement.rationale[0].id == "test_water_tree"

def test_create_placements():
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

    rules = [rule]

    allowed_zone = build_allowed_zone(
        features,
        rules
    )

    placements = create_placements(
        allowed_zone=allowed_zone,
        species_type="tree",
        rules=rules,
        grid_spacing=5.0,
        min_spacing=10.0,
        features=features
    )

    assert len(placements) > 1

    for placement in placements:
        assert allowed_zone.contains(placement.point)
        assert placement.species_type == "tree"


def test_print_placements():
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

    rules = [rule]

    allowed_zone = build_allowed_zone(
        features,
        rules
    )

    placements = create_placements(
        allowed_zone=allowed_zone,
        species_type="tree",
        rules=rules,
        grid_spacing=5.0,
        min_spacing=10.0,
        features=features
    )

    print()
    print("Количество точек:", len(placements))

    for placement in placements:
        print(
            round(placement.point.x, 2),
            round(placement.point.y, 2)
        )

    assert len(placements) > 1


def test_create_plan():
    from shapely.geometry import Polygon

    from greenplan.models import FeatureKind, Rule
    from greenplan.planner.planner import create_plan

    allowed_zone = Polygon([
        (0, 0),
        (50, 0),
        (50, 50),
        (0, 50)
    ])

    rules = [
        Rule(
            id="test_tree",
            object=FeatureKind.PIPE_WATER,
            planting="tree",
            min_distance_m=2.0,
            act="TEST",
            clause="TEST",
            verified=True
        )
    ]
    features = []

    placements = create_plan(
        allowed_zone,
        "tree",
        rules,
        5.0,
        10.0,
        features
    )

    assert len(placements) > 0
    assert all(
        placement.species_type == "tree"
        for placement in placements
    )


def test_placements_have_required_spacing():
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

    rules = [rule]

    allowed_zone = build_allowed_zone(
        features,
        rules
    )

    placements = create_placements(
        allowed_zone=allowed_zone,
        species_type="tree",
        rules=rules,
        grid_spacing=5.0,
        min_spacing=10.0,
        features=features
    )

    for i in range(len(placements)):
        for j in range(i + 1, len(placements)):
            distance = placements[i].point.distance(
                placements[j].point
            )

            assert distance >= 10.0


def test_placements_have_rationale():
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

    rules = [rule]

    allowed_zone = build_allowed_zone(
        features,
        rules
    )

    placements = create_placements(
        allowed_zone=allowed_zone,
        species_type="tree",
        rules=rules,
        grid_spacing=5.0,
        min_spacing=10.0,
        features=features
    )

    assert len(placements) > 0

    for placement in placements:
        assert len(placement.rationale) == 1
        assert placement.rationale[0].id == "test_water_tree"


def test_rule_check():
    rule = Rule(
        id="test_water_tree",
        object=FeatureKind.PIPE_WATER,
        planting="tree",
        min_distance_m=2.0,
        act="TEST",
        clause="TEST",
        verified=True
    )

    check = RuleCheck(
        rule=rule,
        status="allowed",
        distance_m=3.5
    )

    assert check.rule.id == "test_water_tree"
    assert check.status == "allowed"
    assert check.distance_m == 3.5


def test_check_rule():
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

    check = check_rule(
        Point(20, 10),
        features,
        rule
    )

    assert check.rule.id == "test_water_tree"
    assert check.status == "allowed"
    assert check.distance_m is not None
    assert check.distance_m >= 2.0

