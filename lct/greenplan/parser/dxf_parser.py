import ezdxf

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from ezdxf.disassemble import recursive_decompose
from greenplan.models import Feature, FeatureKind


LAYER_KIND = {
    "PIPE_WATER": FeatureKind.PIPE_WATER,
    "PIPE_GAS": FeatureKind.PIPE_GAS,
    "CABLE": FeatureKind.CABLE,
    "BUILDING": FeatureKind.BUILDING,
    "ROAD": FeatureKind.ROAD,
    "POWERLINE": FeatureKind.POWERLINE,
    "SITE_BOUNDARY": FeatureKind.SITE_BOUNDARY,
    "ГРАНИЦА_ЗАКАЗА": FeatureKind.SITE_BOUNDARY,
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


def insert_to_feature(entity, doc) -> Feature | None:
    if entity.dxftype() != "INSERT":
        return None

    if entity.dxf.name == "УРНА__":
        return Feature(
            geom=Point(
                entity.dxf.insert.x,
                entity.dxf.insert.y
            ),
            kind=FeatureKind.BIN,
            source_layer=entity.dxf.layer
        )

    if entity.dxf.name != "*U476":
        return None

    if entity.dxf.layer != "ДВ_ГП_П_МАФ":
        return None

    geometries = []

    for item in recursive_decompose([entity]):
        if item.dxftype() != "LWPOLYLINE":
            continue

        if not item.closed:
            continue

        points = [
            (point[0], point[1])
            for point in item.get_points()
        ]

        if len(points) < 3:
            continue

        polygon = Polygon(points)

        if not polygon.is_empty and polygon.is_valid:
            geometries.append(polygon)

    if not geometries:
        return None

    geometry = unary_union(geometries)

    return Feature(
        geom=geometry,
        kind=FeatureKind.MAF,
        source_layer=entity.dxf.layer
    )


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

        if feature is None and entity.dxftype() == "INSERT":
            feature = insert_to_feature(
                entity,
                doc
            )

        if feature is not None:
            features.append(feature)

    return features