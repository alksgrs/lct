import ezdxf

from greenplan.models import FeatureKind
from greenplan.parser.dxf_parser import parse_dxf
from tests.paths import LAYERS


def make_dxf(path):
    doc = ezdxf.new("R2010")
    block = doc.blocks.new("КОНТЕЙНЕРНАЯ_ПЛОЩАДКА_НА_3")
    block.add_lwpolyline([(0, 0), (4, 0), (4, 3), (0, 3)], close=True)
    msp = doc.modelspace()
    msp.add_blockref("КОНТЕЙНЕРНАЯ_ПЛОЩАДКА_НА_3", (10, 10), dxfattribs={"layer": "ХЗ_1"})
    msp.add_line((0, 0), (5, 5), dxfattribs={"layer": "ХЗ_1"})
    msp.add_text("Условные обозначения", dxfattribs={"layer": "НЕПОНЯТНО"})
    msp.add_mtext("Примечание", dxfattribs={"layer": "НЕПОНЯТНО"})
    doc.saveas(path)


def test_block_name_types_insert_on_unknown_layer(tmp_path):
    path = tmp_path / "plan.dxf"
    make_dxf(path)
    parsed = parse_dxf(str(path), LAYERS)
    maf = [f for f in parsed.features if f.kind == FeatureKind.MAF]
    assert len(maf) == 1
    assert maf[0].match_method == "block"
    assert abs(maf[0].geom.area - 12) < 1e-6
    layer = next(l for l in parsed.layers if l["layer"] == "ХЗ_1")
    assert layer["kind"] is None
    assert layer["typed_by_block"] == 1


def test_text_only_layer_is_annotation(tmp_path):
    path = tmp_path / "plan.dxf"
    make_dxf(path)
    parsed = parse_dxf(str(path), LAYERS)
    layer = next(l for l in parsed.layers if l["layer"] == "НЕПОНЯТНО")
    assert layer["kind"] == "ANNOTATION"
    assert layer["method"] == "content"
    assert "НЕПОНЯТНО" not in {u["layer"] for u in parsed.unresolved_layers}
