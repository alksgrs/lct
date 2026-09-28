from shapely.geometry import Polygon
from shapely.ops import unary_union
from greenplan.models import Feature, FeatureKind, Rule


def get_site_boundary(features: list[Feature]) -> Polygon:
    for feature in features:
        if feature.kind == FeatureKind.SITE_BOUNDARY:
            if isinstance(feature.geom, Polygon):
                return feature.geom

    raise ValueError("SITE_BOUNDARY not found")

def get_features_inside_site(
    features: list[Feature]
) -> list[Feature]:
    site = get_site_boundary(features)

    result = []

    for feature in features:
        if feature.kind == FeatureKind.SITE_BOUNDARY:
            continue

        if site.intersects(feature.geom):
            result.append(feature)

    return result


def build_allowed_zone(
    features: list[Feature],
    rules: list[Rule]
):
    site = get_site_boundary(features)

    allowed_zone = site

    for rule in rules:
        for feature in features:
            if feature.kind != rule.object:
                continue

            forbidden_zone = feature.geom.buffer(
                rule.min_distance_m
            )

            allowed_zone = allowed_zone.difference(
                forbidden_zone
            )

    return allowed_zone


def apply_bin_offset(allowed_zone, features, offset: float):
    bins = [
        feature.geom
        for feature in features
        if feature.kind == FeatureKind.BIN
    ]

    if not bins or offset <= 0:
        return allowed_zone

    forbidden_zone = build_forbidden_zone(
        bins,
        offset
    )

    return allowed_zone.difference(forbidden_zone)


def build_forbidden_zone(
    geometries,
    distance: float
):
    if distance < 0:
        raise ValueError(
            "Distance must be non-negative"
        )

    if not geometries:
        return Polygon()

    buffers = [
        geometry.buffer(distance)
        for geometry in geometries
    ]

    return unary_union(buffers)

