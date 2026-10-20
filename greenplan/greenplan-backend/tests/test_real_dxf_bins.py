from tests.paths import GENPLAN
from greenplan.parser.dxf_parser import read_dxf
from greenplan.constraints.constraints import get_features_inside_site
from greenplan.models import FeatureKind


def test_real_dxf_has_114_bins_inside_site():
    features = read_dxf(
        GENPLAN
    )

    site_features = get_features_inside_site(features)

    bins = [
        feature
        for feature in site_features
        if feature.kind == FeatureKind.BIN
    ]

    assert len(bins) == 114

    for feature in bins:
        assert feature.geom.geom_type == "Point"

