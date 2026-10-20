from shapely.geometry.base import BaseGeometry

PRECISION = 2
SIMPLIFY_M = 0.02


def _xy(coords):
    return [[round(float(x), PRECISION), round(float(y), PRECISION)] for x, y, *_ in coords]


def geometry_to_json(geometry: BaseGeometry | None, simplify: float = SIMPLIFY_M) -> dict | None:
    if geometry is None or geometry.is_empty:
        return None
    if simplify and geometry.geom_type != "Point":
        geometry = geometry.simplify(simplify, preserve_topology=True)
        if geometry.is_empty:
            return None
    kind = geometry.geom_type
    if kind == "Point":
        return {"type": "Point", "coordinates": _xy(geometry.coords)[0]}
    if kind == "LineString":
        return {"type": "LineString", "coordinates": _xy(geometry.coords)}
    if kind == "Polygon":
        rings = [geometry.exterior, *geometry.interiors]
        return {"type": "Polygon", "coordinates": [_xy(ring.coords) for ring in rings]}
    if kind == "MultiLineString":
        return {"type": "MultiLineString", "coordinates": [_xy(line.coords) for line in geometry.geoms]}
    if kind == "MultiPolygon":
        return {
            "type": "MultiPolygon",
            "coordinates": [
                [_xy(ring.coords) for ring in (polygon.exterior, *polygon.interiors)]
                for polygon in geometry.geoms
            ],
        }
    if kind == "MultiPoint":
        return {"type": "MultiPoint", "coordinates": [_xy(point.coords)[0] for point in geometry.geoms]}
    if kind == "GeometryCollection":
        parts = [geometry_to_json(part, 0) for part in geometry.geoms]
        parts = [part for part in parts if part]
        return {"type": "GeometryCollection", "geometries": parts} if parts else None
    return None
