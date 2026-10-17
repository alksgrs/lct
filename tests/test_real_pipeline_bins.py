from shapely.ops import unary_union

from greenplan.constraints.constraints import get_features_inside_site
from greenplan.models import FeatureKind
from greenplan.parser.dxf_parser import read_dxf
from greenplan.pipeline import build_plan


def test_real_pipeline_respects_bin_offset():
    input_path = r"_06_10000176_Генплан_Олимп.dxf"

    features = read_dxf(input_path)
    site_features = get_features_inside_site(features)

    bins = [
        feature.geom
        for feature in site_features
        if feature.kind == FeatureKind.BIN
    ]

    bin_zone = unary_union([
        point.buffer(0.1)
        for point in bins
    ])

    placements, rejections = build_plan(
        input_path=input_path,
        rules_path=r"data/rules/sp42.yaml",
        planting_path=r"data/rules/planting.yaml",
        species_type="tree"
    )

    for placement in placements:
        assert not bin_zone.contains(placement.point)

