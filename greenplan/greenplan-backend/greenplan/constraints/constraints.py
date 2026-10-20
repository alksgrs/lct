from statistics import median

from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

from greenplan.models import Feature, FeatureKind, Rule, RuleKind

OUTLIER_FACTOR = 10.0
HULL_MARGIN_M = 2.0
HULL_LIMIT_M2 = 250_000
CORRIDOR_M = 20.0

BOUNDARY_LABELS = {
    "argument": "контур со слоя, указанного пользователем",
    "layer": "замкнутый контур со слоя границы",
    "convex_hull": "выпуклая оболочка объектов чертежа",
    "corridor": "полоса 20 м вдоль объектов чертежа",
}


class BoundaryResult(tuple):
    def __new__(cls, polygon, method, outliers=0):
        instance = super().__new__(cls, (polygon, method))
        instance.outliers = outliers
        return instance


def _closed_polygons(features):
    polygons = []
    for feature in features:
        geometry = feature.geom
        if isinstance(geometry, Polygon) and not geometry.is_empty:
            polygons.append(geometry)
        elif isinstance(geometry, MultiPolygon):
            polygons.extend(geometry.geoms)
        elif geometry.geom_type == "LineString" and len(geometry.coords) >= 3:
            polygon = Polygon(geometry.coords).buffer(0)
            if polygon.geom_type == "Polygon" and polygon.area > 0:
                polygons.append(polygon)
    return polygons


def trim_outliers(geometries, factor: float = OUTLIER_FACTOR):
    if len(geometries) < 4:
        return list(geometries), 0
    centers = [geometry.centroid for geometry in geometries]
    cx = median(point.x for point in centers)
    cy = median(point.y for point in centers)
    distances = [((p.x - cx) ** 2 + (p.y - cy) ** 2) ** 0.5 for p in centers]
    limit = max(median(distances) * factor, 50.0)
    kept = [g for g, d in zip(geometries, distances) if d <= limit]
    return kept, len(geometries) - len(kept)


def get_site_boundary(features: list[Feature], boundary_layer: str | None = None):
    if not features:
        raise ValueError("В DXF не найдено распознанных объектов, границу участка определить нельзя.")

    if boundary_layer:
        layer = boundary_layer.casefold()
        polygons = _closed_polygons([f for f in features if f.source_layer.casefold() == layer])
        if not polygons:
            raise ValueError(f"На слое «{boundary_layer}» нет замкнутого контура границы.")
        return BoundaryResult(max(polygons, key=lambda p: p.area), "argument")

    boundaries = [f for f in features if f.kind == FeatureKind.SITE_BOUNDARY]
    preferred = [f for f in boundaries if f.match_method in ("override", "config")]
    polygons = _closed_polygons(preferred) or _closed_polygons(boundaries)
    if polygons:
        return BoundaryResult(max(polygons, key=lambda p: p.area), "layer")

    geometries = [f.geom for f in features if f.geom is not None and not f.geom.is_empty]
    kept, outliers = trim_outliers(geometries)
    if not kept:
        raise ValueError("В DXF нет геометрии, по которой можно определить границу участка.")
    hull = unary_union(kept).convex_hull
    if hull.is_empty or hull.geom_type != "Polygon" or hull.area <= 0:
        raise ValueError("Объектов чертежа недостаточно, чтобы построить границу участка.")
    if hull.area <= HULL_LIMIT_M2:
        return BoundaryResult(hull.buffer(HULL_MARGIN_M), "convex_hull", outliers)
    corridor = unary_union([g.buffer(CORRIDOR_M) for g in kept]).intersection(hull.buffer(HULL_MARGIN_M))
    return BoundaryResult(corridor, "corridor", outliers)


def get_features_inside_site(features: list[Feature]) -> list[Feature]:
    site, _ = get_site_boundary(features)
    return [f for f in features if f.kind != FeatureKind.SITE_BOUNDARY and site.intersects(f.geom)]


def build_ban_zone(features: list[Feature], rules: list[Rule]):
    zones = []
    for rule in rules:
        if rule.kind != RuleKind.BAN:
            continue
        zones.extend(f.geom.buffer(rule.zone_m) for f in features if f.kind == rule.object)
    return unary_union(zones) if zones else Polygon()


def build_allowed_zone(features: list[Feature], rules: list[Rule]):
    site, _ = get_site_boundary(features)
    allowed = site
    for rule in rules:
        if rule.kind == RuleKind.NOT_REGULATED:
            continue
        for feature in features:
            if feature.kind == rule.object:
                allowed = allowed.difference(feature.geom.buffer(rule.limit_m))
    return allowed


def apply_bin_offset(allowed_zone, features, offset: float):
    bins = [f.geom for f in features if f.kind == FeatureKind.BIN]
    if not bins or offset <= 0:
        return allowed_zone
    return allowed_zone.difference(build_forbidden_zone(bins, offset))


def build_forbidden_zone(geometries, distance: float):
    if distance < 0:
        raise ValueError("Distance must be non-negative")
    if not geometries:
        return Polygon()
    return unary_union([geometry.buffer(distance) for geometry in geometries])
