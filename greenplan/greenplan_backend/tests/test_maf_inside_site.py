from tests.paths import GENPLAN
from greenplan.constraints.constraints import get_features_inside_site
from greenplan.models import FeatureKind
from greenplan.parser.dxf_parser import read_dxf


def test_maf_features_inside_site():
    features = read_dxf(
        GENPLAN
    )

    site_features = get_features_inside_site(
        features
    )

    mafs = [
        feature
        for feature in site_features
        if feature.kind == FeatureKind.MAF
    ]

    assert len(mafs) == 109

