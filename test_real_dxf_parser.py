from pathlib import Path

from greenplan.models import FeatureKind
from greenplan.parser.dxf_parser import read_dxf


def test_read_real_dxf():
    project_root = Path(__file__).resolve().parent.parent
    dxf_path = project_root / "_06_10000176_Генплан_Олимп.dxf"

    features = read_dxf(str(dxf_path))

    assert features

    site_boundaries = [
        feature
        for feature in features
        if feature.kind == FeatureKind.SITE_BOUNDARY
    ]

    bins = [
        feature
        for feature in features
        if feature.kind == FeatureKind.BIN
    ]

    mafs = [
        feature
        for feature in features
        if feature.kind == FeatureKind.MAF
    ]

    assert len(site_boundaries) == 1
    assert len(bins) == 122
    assert len(mafs) == 119

