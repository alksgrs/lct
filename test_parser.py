from pathlib import Path

from greenplan.models import FeatureKind
from greenplan.parser.dxf_parser import read_dxf
from greenplan.models import FeatureKind
from greenplan.parser.dxf_parser import layer_to_kind
from greenplan.config.layers import load_layer_rules


def test_parser_layer_mapping_from_yaml():
    rules = load_layer_rules(
        "data/config/layers.yaml"
    )

    assert layer_to_kind(
        "ГРАНИЦА_ЗАКАЗА",
        rules
    ) == FeatureKind.SITE_BOUNDARY

    assert layer_to_kind(
        "TEST_КАНАЛИЗАЦИЯ",
        rules
    ) == FeatureKind.PIPE_SEWER

    assert layer_to_kind(
        "TEST_ВОДОСТОК",
        rules
    ) == FeatureKind.PIPE_DRAINAGE


def test_read_test_dxf():
    project_root = Path(__file__).resolve().parent.parent
    dxf_path = project_root / "test.dxf"

    features = read_dxf(str(dxf_path))

    assert len(features) == 3

    site = next(
        feature
        for feature in features
        if feature.kind == FeatureKind.SITE_BOUNDARY
    )

    building = next(
        feature
        for feature in features
        if feature.kind == FeatureKind.BUILDING
    )

    pipe = next(
        feature
        for feature in features
        if feature.kind == FeatureKind.PIPE_WATER
    )

    assert site.geom.geom_type == "Polygon"
    assert building.geom.geom_type == "Polygon"
    assert pipe.geom.geom_type == "LineString"

