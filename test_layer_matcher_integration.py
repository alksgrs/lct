import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from greenplan.config.layer_matcher import LayerMatcher
from greenplan.config.overrides import parse_override
from greenplan.models import FeatureKind
from greenplan.parser import dxf_parser
from greenplan.parser.dxf_parser import parse_dxf, read_dxf
from greenplan.writer.json_writer import write_placements_json

DXF_NAME = "_06_10000176_Генплан_Олимп.dxf"


def find_olimp_dxf():
    candidates = []
    if os.environ.get("GREENPLAN_TEST_DXF"):
        candidates.append(Path(os.environ["GREENPLAN_TEST_DXF"]))

    root = Path(__file__).resolve().parent.parent
    candidates += [
        Path(__file__).resolve().parent / "data" / DXF_NAME,
        root / "data" / DXF_NAME,
        root / DXF_NAME,
    ]

    for path in candidates:
        if path.is_file():
            return path

    return None


@pytest.fixture(scope="module")
def olimp():
    path = find_olimp_dxf()
    if path is None:
        pytest.skip(
            f"нет файла {DXF_NAME}: положите в tests/data/ "
            "или укажите путь в GREENPLAN_TEST_DXF"
        )
    return parse_dxf(str(path))


def test_olimp_roads(olimp):
    # считаются сущности modelspace на слоях типа ROAD (INSERT, HATCH,
    # LWPOLYLINE и т.д.), а не только те, что парсер превращает в фичи
    assert olimp.entity_counts_by_kind.get("ROAD", 0) >= 200


def test_olimp_road_features_exist(olimp):
    kinds = Counter(f.kind for f in olimp.features)
    assert kinds[FeatureKind.ROAD] >= 1


def test_olimp_site_boundary(olimp):
    kinds = Counter(f.kind for f in olimp.features)
    assert kinds[FeatureKind.SITE_BOUNDARY] >= 1


def test_olimp_feature_invariants(olimp):
    for feature in olimp.features:
        assert feature.match_method in ("override", "dictionary", "fuzzy")
        assert 0.0 < feature.confidence <= 1.0
        assert feature.kind != FeatureKind.UNKNOWN


# ---- логика подключения на подменённом документе (без реального DXF) ----

def fake_line(layer):
    return SimpleNamespace(
        dxftype=lambda: "LINE",
        dxf=SimpleNamespace(
            layer=layer,
            start=SimpleNamespace(x=0, y=0),
            end=SimpleNamespace(x=1, y=1),
        ),
    )


def fake_doc(layers_and_counts):
    entities = [
        fake_line(layer)
        for layer, count in layers_and_counts.items()
        for _ in range(count)
    ]
    return SimpleNamespace(modelspace=lambda: entities)


def parse_fake(layers_and_counts, **kwargs):
    with patch.object(
        dxf_parser.ezdxf, "readfile",
        return_value=fake_doc(layers_and_counts)
    ):
        return parse_dxf("fake.dxf", **kwargs)


def test_annotation_and_unknown_are_not_features():
    result = parse_fake({
        "БОРТ_1": 3,
        "ГРАНИЦА_ЗАКАЗА": 1,
        "ТЕКСТ_ОБЩИЙ": 5,
        "ZZZ_QQQ": 4,
    })

    assert {f.source_layer for f in result.features} == {
        "БОРТ_1", "ГРАНИЦА_ЗАКАЗА"
    }
    assert len(result.features) == 4


def test_unresolved_layers_fields():
    result = parse_fake({"БОРТ_1": 1, "ZZZ_QQQ": 4, "ЩЩЩ_ЮЮЮ": 2})

    assert [u["layer"] for u in result.unresolved_layers] == [
        "ZZZ_QQQ", "ЩЩЩ_ЮЮЮ"
    ]
    first = result.unresolved_layers[0]
    assert set(first) == {"layer", "entity_count", "tokens"}
    assert first["entity_count"] == 4
    assert first["tokens"] == ["ZZZ", "QQQ"]


def test_feature_gets_confidence_and_method():
    result = parse_fake({"БОРТ_1": 1})
    feature = result.features[0]

    assert feature.kind == FeatureKind.ROAD
    assert feature.match_method == "dictionary"
    assert feature.confidence == 1.0


def test_override_is_applied():
    result = parse_fake(
        {"ZZZ_QQQ": 2},
        overrides={"ZZZ_QQQ": "ROAD"}
    )

    assert result.unresolved_layers == []
    assert [f.match_method for f in result.features] == ["override"] * 2


def test_read_dxf_still_returns_list():
    with patch.object(
        dxf_parser.ezdxf, "readfile",
        return_value=fake_doc({"БОРТ_1": 2})
    ):
        features = read_dxf("fake.dxf", "data/config/layers.yaml")

    assert isinstance(features, list)
    assert len(features) == 2


def test_entity_counts_by_kind_counts_all_entities():
    result = parse_fake({
        "БОРТ_1": 3,
        "БОРТ_2": 2,
        "ТЕКСТ_ОБЩИЙ": 5,
        "ZZZ_QQQ": 4,
    })

    assert result.entity_counts_by_kind["ROAD"] == 5
    assert result.entity_counts_by_kind["ANNOTATION"] == 5
    assert "UNKNOWN" not in result.entity_counts_by_kind


def test_unresolved_layers_reach_json_report():
    unresolved = [{"layer": "ZZZ_QQQ", "entity_count": 4, "tokens": ["ZZZ", "QQQ"]}]

    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "out.json")
        write_placements_json([], out, "in.dxf", "tree", [], [], unresolved)
        with open(out, encoding="utf-8") as file:
            data = json.load(file)

        assert data["unresolved_layers"] == unresolved

        write_placements_json([], out, "in.dxf", "tree")
        with open(out, encoding="utf-8") as file:
            assert json.load(file)["unresolved_layers"] == []


def test_dictionary_extension_from_olimp():
    matcher = LayerMatcher()
    expected = {
        "_ТИП_1__РЕМ__ЩМА_": "ROAD",
        "_ГЗН-ГЗН": "EXISTING_GREEN",
        "СИП_2А": "POWERLINE",
        "ДВ_ГП_П_СТЕЛА": "MAF",
        "ВСПОМОГАТЕЛЬНЫЙ_СЛОЙ_В_БЛО": "ANNOTATION",
    }
    for layer, kind in expected.items():
        assert matcher.match(layer).kind == kind, layer

    # прежнее поведение не изменилось: ПЧ/АБ по-прежнему приоритетнее ГЗН
    assert matcher.match("_ГЗН-АБ_ПЧ").kind == "ROAD"


def test_parse_override():
    assert parse_override("ГП_300_300=ROAD") == ("ГП_300_300", "ROAD")
    assert parse_override(" ГП1__300Х150_ = road ") == ("ГП1__300Х150_", "ROAD")
    assert parse_override("ВСПОМ=ANNOTATION") == ("ВСПОМ", "ANNOTATION")

    for bad in ("ГП_300_300", "=ROAD", "ГП_300_300=ROADD", "ГП=UNKNOWN"):
        with pytest.raises(ValueError):
            parse_override(bad)


def test_override_makes_curb_layers_roads():
    result = parse_fake(
        {"ГП_300_300": 3, "ГП1__300Х150_": 2},
        overrides={
            "ГП_300_300": "ROAD",
            "ГП1__300Х150_": "ROAD",
        }
    )

    assert result.unresolved_layers == []
    assert [f.kind for f in result.features] == [FeatureKind.ROAD] * 5

