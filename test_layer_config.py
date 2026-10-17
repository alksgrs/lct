from pathlib import Path

from greenplan.config.layers import (
    get_layer_kind,
    load_layer_rules
)
from greenplan.models import FeatureKind


def test_load_layer_rules():
    project_root = Path(__file__).resolve().parent.parent
    path = project_root / "data" / "config" / "layers.yaml"

    rules = load_layer_rules(str(path))

    assert rules


def test_layer_kind():
    project_root = Path(__file__).resolve().parent.parent
    path = project_root / "data" / "config" / "layers.yaml"

    rules = load_layer_rules(str(path))

    assert get_layer_kind(
        "ГРАНИЦА_ЗАКАЗА",
        rules
    ) == FeatureKind.SITE_BOUNDARY

    assert get_layer_kind(
        "_ГП_КОЛОДЦЫ_РЕМОНТ_КАНАЛИЗ",
        rules
    ) == FeatureKind.PIPE_SEWER

    assert get_layer_kind(
        "_ГП_КОЛОДЦЫ_ВОДОСТОКА_РЕШЕ",
        rules
    ) == FeatureKind.PIPE_DRAINAGE


def test_unknown_layer():
    project_root = Path(__file__).resolve().parent.parent
    path = project_root / "data" / "config" / "layers.yaml"

    rules = load_layer_rules(str(path))

    assert get_layer_kind(
        "КАКОЙ_ТО_НЕИЗВЕСТНЫЙ_СЛОЙ",
        rules
    ) == FeatureKind.UNKNOWN

def test_lighting_layer():
    project_root = Path(__file__).resolve().parent.parent
    path = project_root / "data" / "config" / "layers.yaml"

    rules = load_layer_rules(str(path))

    assert get_layer_kind(
        "ДВ_ГП_П_НО_СВЕТИЛЬНИК_КОНТ",
        rules
    ) == FeatureKind.LIGHTING

