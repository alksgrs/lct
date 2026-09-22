from shapely.geometry import Polygon

from greenplan.models import Feature, FeatureKind, Rule


def get_site_boundary(features: list[Feature]) -> Polygon:
    for feature in features:
        if feature.kind == FeatureKind.SITE_BOUNDARY:
            if isinstance(feature.geom, Polygon):
                return feature.geom

    raise ValueError("SITE_BOUNDARY not found")


def build_allowed_zone(
    features: list[Feature],
    rule: Rule
) -> Polygon:
    site = get_site_boundary(features)

    forbidden_zone = None

    for feature in features:
        if feature.kind != rule.object:
            continue

        buffer = feature.geom.buffer(rule.min_distance_m)

        if forbidden_zone is None:
            forbidden_zone = buffer
        else:
            forbidden_zone = forbidden_zone.union(buffer)

    if forbidden_zone is None:
        return site

    allowed_zone = site.difference(forbidden_zone)

    return allowed_zone