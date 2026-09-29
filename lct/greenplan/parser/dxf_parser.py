import ezdxf

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from ezdxf.disassemble import recursive_decompose
from greenplan.models import Feature, FeatureKind
from pathlib import Path

from greenplan.config.layers import load_layer_rules, get_layer_kind


def layer_to_kind(layer_name, layer_rules):
    return get_layer_kind(
        layer_name,
        layer_rules
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


def entity_to_feature(entity, layer_rules):
    layer_name = entity.dxf.layer
    kind = layer_to_kind(
        entity.dxf.layer,
        layer_rules
    )

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


def read_dxf(
    path,
    layers_path="data/config/layers.yaml"
):
    layer_rules = load_layer_rules(
        layers_path
    )

    doc = ezdxf.readfile(path)
    modelspace = doc.modelspace()

    features = []

    for entity in modelspace:
        if entity.dxftype() == "INSERT":
            feature = insert_to_feature(
                entity,
                doc
            )
        else:
            feature = entity_to_feature(
                entity,
                layer_rules
            )

        if feature is not None:
            features.append(feature)

    return features

