from greenplan.config.layer_matcher import LayerMatcher, similarity, tokenize
from greenplan.models import FeatureKind
from greenplan.parser.dxf_parser import layer_to_kind, load_layer_rules
from tests.paths import LAYERS


def kind_of(layer, layers=None):
    matcher = LayerMatcher().fit(layers or [layer])
    return matcher.match(layer).kind


def test_tokenize_drops_xref_prefix_and_numbers():
    assert tokenize("$0$ДВ_ГП_П_МАФ") == ("ДВ", "ГП", "МАФ")
    assert tokenize("1Х63ММ_ОСВЕЩЕНИЕ") == ("ММ", "ОСВЕЩЕНИЕ")
    assert tokenize("ЭН_ОПОРА_К1_LED") == ("ЭН", "ОПОРА", "LED")


def test_reference_labels_are_annotation_not_cable():
    assert kind_of("ССЫЛКА_КЛ") == "ANNOTATION"
    assert kind_of("ЭН_ВЫНОСКИ_НОМЕРА_ОПОРЫ") == "ANNOTATION"


def test_lawn_is_not_gas_pipe():
    rules = load_layer_rules(LAYERS)
    assert layer_to_kind("ГАЗОН", rules) != FeatureKind.PIPE_GAS
    assert layer_to_kind("ДВ_ГП_ГАЗОН", rules) != FeatureKind.PIPE_GAS
    assert kind_of("ГАЗОН") == "EXISTING_GREEN"
    assert kind_of("СЕТИ_ГАЗ") == "PIPE_GAS"


def test_supports_and_poles_are_lighting():
    assert kind_of("ЭН_СУЩ_ОПОРА_К1_LED") == "LIGHTING"
    assert kind_of("ОПОРЫ_НО") == "LIGHTING"


def test_overhead_line_is_powerline():
    assert kind_of("ЭН_ВЛ_НО") == "POWERLINE"
    assert kind_of("СИП_0.4") == "POWERLINE"


def test_fuzzy_match_catches_typo():
    assert similarity("ТРОТУРА", "ТРОТУАР") >= 0.62
    match = LayerMatcher().fit(["ТРОТУРА"]).match("ТРОТУРА")
    assert match.kind == "PAVEMENT"
    assert match.method == "fuzzy"


def test_common_project_prefix_is_ignored():
    layers = ["ПР_ЗДАНИЕ", "ПР_ДОРОГА", "ПР_КАНАЛ", "ПР_ТРОТУАР", "ПР_НЕЧТО"]
    matcher = LayerMatcher().fit(layers)
    assert "ПР" in matcher.service
    assert matcher.match("ПР_НЕЧТО").kind == "UNKNOWN"


def test_override_wins():
    matcher = LayerMatcher(overrides={"ПР_НЕЧТО": "PIPE_HEAT"}).fit(["ПР_НЕЧТО"])
    match = matcher.match("ПР_НЕЧТО")
    assert match.kind == "PIPE_HEAT"
    assert match.method == "override"


def test_terrain_and_tram_layers():
    assert kind_of("ГП_ОТКОС") == "SLOPE"
    assert kind_of("ПОДПОРНАЯ_СТЕНКА") == "RETAINING_WALL"
    assert kind_of("ТРАМВАЙНЫЕ_ПУТИ") == "TRAM_TRACK"


def test_moscow_pavement_types_and_kerbs():
    rules = load_layer_rules(LAYERS)
    assert layer_to_kind("_ТИП_2__РЕМ__МЗ_А_Б_", rules) == FeatureKind.ROAD
    assert layer_to_kind("_ТИП_5__РЕМ__ТР_ИЗ_А_Б_", rules) == FeatureKind.PAVEMENT
    assert layer_to_kind("_ПЛ_ТР-ПЛ_ТР", rules) == FeatureKind.PAVEMENT
    assert layer_to_kind("ГП1__300Х150_", rules) == FeatureKind.ROAD
    assert layer_to_kind("ДВ_ГП_П_МАФ", rules) is None


def test_demolition_and_stairs():
    assert kind_of("ЭН_ДЕМОНТАЖ") == "ANNOTATION"
    assert kind_of("_РАЗБОРКА") == "ANNOTATION"
    assert kind_of("_ГП_ВЕРТИКАЛКА") == "ANNOTATION"
    assert kind_of("ЛЕСТНИЦЫ") == "MAF"
    assert kind_of("ПАНДУС") == "MAF"
