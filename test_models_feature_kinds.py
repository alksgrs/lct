from greenplan.models import FeatureKind


def test_pipe_heat_feature_kind():
    assert FeatureKind.PIPE_HEAT.value == "PIPE_HEAT"


def test_sewer_feature_kind():
    assert FeatureKind.PIPE_SEWER.value == "PIPE_SEWER"


def test_drainage_feature_kind():
    assert FeatureKind.PIPE_DRAINAGE.value == "PIPE_DRAINAGE"