import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shapely.geometry import Polygon

from greenplan.constraints.constraints import get_site_boundary
from greenplan.models import FeatureKind
from greenplan.parser.dxf_parser import parse_dxf

parsed = parse_dxf(sys.argv[1])
site = [f for f in parsed.features if f.kind == FeatureKind.SITE_BOUNDARY]
chosen = get_site_boundary(parsed.features)

for i, f in enumerate(site):
    g = f.geom
    b = g.bounds
    area = f"{g.area:.0f}" if isinstance(g, Polygon) else "-"
    mark = "  <== ВЫБРАНА" if g is chosen else ""
    print(
        f"{i}: слой {f.source_layer}, {g.geom_type}, площадь {area}, "
        f"x {b[0]:.1f}..{b[2]:.1f}, y {b[1]:.1f}..{b[3]:.1f}{mark}"
    )

