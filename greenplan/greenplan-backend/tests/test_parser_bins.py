from tests.paths import GENPLAN
from greenplan.models import FeatureKind
from greenplan.parser.dxf_parser import read_dxf


def test_parser_reads_bins():
    features = read_dxf(
        GENPLAN
    )

    bins = [
        feature
        for feature in features
        if feature.kind == FeatureKind.BIN
    ]

    assert len(bins) == 122

    for feature in bins:
        assert feature.geom.geom_type == "Point"

