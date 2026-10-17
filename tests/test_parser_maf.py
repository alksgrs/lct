from greenplan.models import FeatureKind
from greenplan.parser.dxf_parser import read_dxf


def test_parser_reads_maf():
    features = read_dxf(
        r"_06_10000176_Генплан_Олимп.dxf"
    )

    maf_features = [
        feature
        for feature in features
        if feature.kind == FeatureKind.MAF
    ]

    assert len(maf_features) == 119

    for feature in maf_features:
        assert feature.geom.geom_type == "Polygon"
        assert feature.geom.is_valid
        assert feature.geom.area > 0

