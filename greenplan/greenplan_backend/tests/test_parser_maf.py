from collections import Counter

from tests.paths import GENPLAN
from greenplan.models import FeatureKind
from greenplan.parser.dxf_parser import read_dxf


def test_parser_reads_maf():
    features = read_dxf(GENPLAN)
    maf_features = [feature for feature in features if feature.kind == FeatureKind.MAF]

    assert len(maf_features) >= 119
    layers = Counter(feature.source_layer for feature in maf_features)
    assert layers.most_common(1)[0][0] == "ДВ_ГП_П_МАФ"

    for feature in maf_features:
        assert feature.geom.geom_type == "Polygon"
        assert feature.geom.is_valid
        assert feature.geom.area > 0
