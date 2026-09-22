import ezdxf

from shapely.geometry import LineString, Polygon

from greenplan.models import Feature, FeatureKind


LAYER_KIND = {
    "PIPE_WATER": FeatureKind.PIPE_WATER,
    "PIPE_GAS": FeatureKind.PIPE_GAS,
    "CABLE": FeatureKind.CABLE,
    "BUILDING": FeatureKind.BUILDING,
    "ROAD": FeatureKind.ROAD,
    "POWERLINE": FeatureKind.POWERLINE,
    "SITE_BOUNDARY": FeatureKind.SITE_BOUNDARY,
}


def layer_to_kind(layer_name: str) -> FeatureKind:
    return LAYER_KIND.get(
        layer_name.upper(),
        FeatureKind.UNKNOWN
    )


def lwpolyline_to_geometry(entity):
    points = [
        (point[0], point[1])
        for point in entity.get_points()
    ]

    if entity.closed:
        if len(points) < 3:
            return None

        return Polygon(points)

    if len(points) < 2:
        return None

    return LineString(points)


def entity_to_feature(entity) -> Feature | None:
    layer_name = entity.dxf.layer
    kind = layer_to_kind(layer_name)

    if entity.dxftype() == "LINE":
        start = entity.dxf.start
        end = entity.dxf.end

        geometry = LineString([
            (start.x, start.y),
            (end.x, end.y)
        ])

    elif entity.dxftype() == "LWPOLYLINE":
        geometry = lwpolyline_to_geometry(entity)

    else:
        return None

    if geometry is None:
        return None

    return Feature(
        geom=geometry,
        kind=kind,
        source_layer=layer_name
    )


def read_dxf(path: str) -> list[Feature]:
    doc = ezdxf.readfile(path)
    modelspace = doc.modelspace()

    features = []

    for entity in modelspace:
        feature = entity_to_feature(entity)

        if feature is not None:
            features.append(feature)

    return features