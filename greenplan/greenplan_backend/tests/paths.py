from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples"
GENPLAN = str(SAMPLES / "_06_10000176_Генплан_Олимп.dxf")
PARKOVAYA = str(SAMPLES / "10001759 НО 3-я Парковая ул.dxf")
KHARKOVSKAYA = str(SAMPLES / "Харьковская АПОТ_2026-01-15.dxf")
TEST_DXF = str(ROOT / "test.dxf")
RULES = str(ROOT / "data" / "rules" / "regulations.yaml")
PLANTING = str(ROOT / "data" / "rules" / "planting.yaml")
LAYERS = str(ROOT / "data" / "config" / "layers.yaml")
