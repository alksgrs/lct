import ezdxf
from ezdxf import const
from shapely.geometry import Point

LAYERS = {
    "tree": ("PLANTING_TREES", 3),
    "shrub": ("PLANTING_SHRUBS", 94),
}
GREENING_LAYERS = {
    "lawn": ("PLANTING_LAWN", 82),
    "hedge": ("PLANTING_HEDGES", 96),
    "flowerbed": ("PLANTING_FLOWERBEDS", 6),
}
SYMBOL_RADIUS = {"tree": 1.0, "shrub": 0.5}
LAWN_PATTERN = ("GRASS", 0.05)
HEDGE_WIDTH_M = 0.8


def write_placements(input_path: str, output_path: str, points: list[Point],
                     layer_name: str = "PLANTING_TREES", symbol_radius: float = 1.0) -> None:
    doc = ezdxf.readfile(input_path)
    if layer_name not in doc.layers:
        doc.layers.add(layer_name)
    modelspace = doc.modelspace()
    for point in points:
        modelspace.add_circle(center=(point.x, point.y), radius=symbol_radius,
                              dxfattribs={"layer": layer_name})
    doc.saveas(output_path)


def _rings(geometry: dict | None):
    if not geometry:
        return []
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"]]
    if geometry["type"] == "MultiPolygon":
        return list(geometry["coordinates"])
    return []


def _write_lawn(modelspace, lawn: dict | None) -> None:
    name, color = GREENING_LAYERS["lawn"]
    pattern, scale = LAWN_PATTERN
    for polygon in _rings(lawn):
        if not polygon or len(polygon[0]) < 4:
            continue
        hatch = modelspace.add_hatch(color=color, dxfattribs={"layer": name})
        hatch.set_pattern_fill(pattern, color=color, scale=scale)
        for index, ring in enumerate(polygon):
            if len(ring) < 4:
                continue
            flags = const.BOUNDARY_PATH_EXTERNAL if index == 0 else const.BOUNDARY_PATH_OUTERMOST
            hatch.paths.add_polyline_path([(x, y) for x, y in ring[:-1]], is_closed=True, flags=flags)
            modelspace.add_lwpolyline([(x, y) for x, y in ring[:-1]], close=True,
                                      dxfattribs={"layer": name, "color": color})


def _write_hedges(modelspace, hedges: list[dict]) -> None:
    name, color = GREENING_LAYERS["hedge"]
    for hedge in hedges:
        points = [(x, y) for x, y in hedge["coordinates"]]
        if len(points) >= 2:
            modelspace.add_lwpolyline(points, dxfattribs={"layer": name, "color": color,
                                                          "const_width": HEDGE_WIDTH_M})


def _write_flowerbeds(modelspace, beds: list[dict]) -> None:
    name, color = GREENING_LAYERS["flowerbed"]
    for bed in beds:
        center = (float(bed["x"]), float(bed["y"]))
        radius = float(bed["radius_m"])
        modelspace.add_circle(center=center, radius=radius, dxfattribs={"layer": name, "color": color})
        hatch = modelspace.add_hatch(color=color, dxfattribs={"layer": name})
        hatch.set_pattern_fill("ANSI37", color=color, scale=0.1)
        path = hatch.paths.add_edge_path(flags=const.BOUNDARY_PATH_EXTERNAL)
        path.add_arc(center, radius, 0, 360)


def write_plan(input_path: str, output_path: str, placements, greening: dict | None = None) -> None:
    doc = ezdxf.readfile(input_path)
    modelspace = doc.modelspace()
    layers = {**LAYERS, **GREENING_LAYERS}
    generated = {name for name, _ in layers.values()}
    for entity in list(modelspace):
        if entity.dxf.layer in generated:
            modelspace.delete_entity(entity)
    for name, color in layers.values():
        if name not in doc.layers:
            doc.layers.add(name, color=color)
    if greening:
        _write_lawn(modelspace, greening.get("lawn"))
        _write_hedges(modelspace, greening.get("hedges", []))
        _write_flowerbeds(modelspace, greening.get("flowerbeds", []))
    for item in placements:
        species = item["species_type"] if isinstance(item, dict) else item.species_type
        x = item["x"] if isinstance(item, dict) else item.point.x
        y = item["y"] if isinstance(item, dict) else item.point.y
        name, _ = LAYERS[species]
        modelspace.add_circle(center=(float(x), float(y)), radius=SYMBOL_RADIUS[species],
                              dxfattribs={"layer": name})
    doc.saveas(output_path)
