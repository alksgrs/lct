from shapely.geometry import Polygon
from shapely.ops import unary_union
from greenplan.models import Feature, FeatureKind, Rule


def get_site_boundary(features: list[Feature], boundary_layer: str | None = None):
    """Return (boundary polygon, detection method)."""
    if not features:
        raise ValueError("В DXF не найдено распознанных объектов; невозможно определить границу участка.")

    if boundary_layer:
        layer_features = [f for f in features if f.source_layer.casefold() == boundary_layer.casefold()]
        polygons = []
        for feature in layer_features:
            geom = feature.geom
            if isinstance(geom, Polygon):
                polygons.append(geom)
            elif geom.geom_type in ("LineString", "MultiLineString") and not geom.is_empty:
                coords = list(geom.coords) if geom.geom_type == "LineString" else []
                if len(coords) >= 3:
                    polygon = Polygon(coords)
                    if polygon.is_valid and polygon.area > 0:
                        polygons.append(polygon)
        if polygons:
            return max(polygons, key=lambda p: p.area), "argument"
        raise ValueError(f"На указанном слое границы «{boundary_layer}» не найден замкнутый контур.")

    boundary_polygons = [f.geom for f in features if f.kind == FeatureKind.SITE_BOUNDARY and isinstance(f.geom, Polygon) and not f.geom.is_empty]
    if boundary_polygons:
        return max(boundary_polygons, key=lambda p: p.area), "layer"

    geometries = [f.geom for f in features if f.geom is not None and not f.geom.is_empty]
    if not geometries:
        raise ValueError("В DXF нет геометрии, по которой можно определить границу участка.")
    hull = unary_union(geometries).convex_hull
    if hull.is_empty or hull.geom_type != "Polygon" or hull.area <= 0:
        raise ValueError("Не удалось определить границу участка: недостаточно геометрии для выпуклой оболочки.")
    return hull.buffer(2), "convex_hull"


def get_features_inside_site(features: list[Feature]) -> list[Feature]:
    site, _ = get_site_boundary(features)
    return [feature for feature in features if feature.kind != FeatureKind.SITE_BOUNDARY and site.intersects(feature.geom)]


def build_allowed_zone(features: list[Feature], rules: list[Rule]):
    site, _ = get_site_boundary(features)
    allowed_zone = site
    for rule in rules:
        for feature in features:
            if feature.kind != rule.object:
                continue
            allowed_zone = allowed_zone.difference(feature.geom.buffer(rule.min_distance_m))
    return allowed_zone


def apply_bin_offset(allowed_zone, features, offset: float):
    bins = [feature.geom for feature in features if feature.kind == FeatureKind.BIN]
    if not bins or offset <= 0:
        return allowed_zone
    return allowed_zone.difference(build_forbidden_zone(bins, offset))


def build_forbidden_zone(geometries, distance: float):
    if distance < 0:
        raise ValueError("Distance must be non-negative")
    if not geometries:
        return Polygon()
    return unary_union([geometry.buffer(distance) for geometry in geometries])
