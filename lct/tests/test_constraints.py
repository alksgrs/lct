from pathlib import Path

from greenplan.parser.dxf_parser import read_dxf


def test_read_features():
    project_root = Path(__file__).resolve().parent.parent
    dxf_path = project_root / "test.dxf"

    features = read_dxf(str(dxf_path))

    for feature in features:
        print(
            feature.source_layer,
            feature.kind,
            feature.geom.geom_type
        )