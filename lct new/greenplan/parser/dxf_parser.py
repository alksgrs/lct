import re
import ezdxf
import yaml

from pathlib import Path
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union, polygonize
from ezdxf.disassemble import recursive_decompose
from collections import Counter
from dataclasses import dataclass, field

from greenplan.models import Feature, FeatureKind
from greenplan.config.layer_matcher import LayerMatcher


@dataclass
class ParseResult:
    features: list[Feature] = field(default_factory=list)
    unresolved_layers: list[dict] = field(default_factory=list)
    entity_counts_by_kind: dict[str, int] = field(default_factory=dict)


def _points_from_path(entity):
    if entity.dxftype() == "LWPOLYLINE":
        return [
            (float(point[0]), float(point[1]))
            for point in entity.get_points()
        ]

    if entity.dxftype() == "POLYLINE":
        return [
            (
                float(vertex.dxf.location.x),
                float(vertex.dxf.location.y),
            )
            for vertex in entity.vertices
        ]

    return []


def lwpolyline_to_geometry(entity):
    points = _points_from_path(entity)

    if len(points) < 2:
        return None

    is_closed = (
        entity.closed
        if entity.dxftype() == "LWPOLYLINE"
        else entity.is_closed
    )

    if is_closed and len(points) >= 3:
        polygon = Polygon(points)

        if polygon.is_valid and not polygon.is_empty:
            return polygon

        fixed = polygon.buffer(0)

        if not fixed.is_empty:
            return fixed

        return None

    return LineString(points)


def _entity_geometry(entity):
    entity_type = entity.dxftype()

    if entity_type in ("LWPOLYLINE", "POLYLINE"):
        return lwpolyline_to_geometry(entity)

    if entity_type == "LINE":
        start = entity.dxf.start
        end = entity.dxf.end

        return LineString([
            (float(start.x), float(start.y)),
            (float(end.x), float(end.y)),
        ])

    if entity_type == "POINT":
        point = entity.dxf.location

        return Point(
            float(point.x),
            float(point.y),
        )

    if entity_type == "CIRCLE":
        center = entity.dxf.center
        radius = float(entity.dxf.radius)

        return Point(
            float(center.x),
            float(center.y),
        ).buffer(radius)

    if entity_type == "ARC":
        try:
            parts = list(recursive_decompose([entity]))
            geometries = []

            for part in parts:
                if part.dxftype() not in (
                    "LINE",
                    "LWPOLYLINE",
                    "POLYLINE",
                ):
                    continue

                geometry = _entity_geometry(part)

                if geometry is not None and not geometry.is_empty:
                    geometries.append(geometry)

            if geometries:
                return unary_union(geometries)

        except Exception:
            return None

    return None


def _insert_geometry(entity):
    geometries = []

    try:
        parts = list(recursive_decompose([entity]))
    except Exception:
        parts = []

    for part in parts:
        try:
            geometry = _entity_geometry(part)
        except Exception:
            continue

        if geometry is not None and not geometry.is_empty:
            geometries.append(geometry)

    polygons = [
        geometry
        for geometry in geometries
        if geometry.geom_type == "Polygon"
    ]

    if polygons:
        merged = unary_union(polygons)

        if merged.geom_type == "Polygon":
            return merged

        if merged.geom_type == "MultiPolygon":
            return max(
                merged.geoms,
                key=lambda polygon: polygon.area,
            )

    lines = [
        geometry
        for geometry in geometries
        if geometry.geom_type in (
            "LineString",
            "MultiLineString",
        )
    ]

    if lines:
        merged_lines = unary_union(lines)
        polygon_parts = list(polygonize(merged_lines))

        if polygon_parts:
            return max(
                polygon_parts,
                key=lambda polygon: polygon.area,
            )

    return None


def load_layer_rules(layers_path):
    path = Path(layers_path)

    with path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}

    rules = []

    for item in config.get("layers", []):
        kind_name = item["kind"]

        if not hasattr(FeatureKind, kind_name):
            raise ValueError(
                f"Неизвестный тип слоя в конфигурации: {kind_name}"
            )

        rules.append((
            re.compile(item["pattern"], re.IGNORECASE),
            FeatureKind[kind_name],
        ))

    return rules


def _resolve_kind(layer_name, rules, matcher):
    for pattern, kind in rules:
        if pattern.search(layer_name):
            return kind, "dictionary", 1.0

    match = matcher.match(layer_name)

    if match.method == "unknown":
        return None, match.method, match.confidence

    if match.kind == "ANNOTATION":
        return "ANNOTATION", match.method, match.confidence

    try:
        return (
            FeatureKind(match.kind),
            match.method,
            match.confidence,
        )
    except ValueError:
        return None, "unknown", 0.0


def _make_feature(geometry, layer_name, kind, confidence, method):
    if geometry is None or geometry.is_empty or kind is None:
        return None

    return Feature(
        geom=geometry,
        kind=kind,
        source_layer=layer_name,
        confidence=confidence,
        match_method=method,
    )


def insert_to_feature(entity, doc, match):
    insertion = entity.dxf.insert

    kind = (
        match[0]
        if isinstance(match, tuple)
        else FeatureKind(match.kind)
    )
    method = (
        match[1]
        if isinstance(match, tuple)
        else match.method
    )
    confidence = (
        match[2]
        if isinstance(match, tuple)
        else match.confidence
    )

    return _make_feature(
        Point(float(insertion.x), float(insertion.y)),
        entity.dxf.layer,
        kind,
        confidence,
        method,
    )


def _feature_for_geometry(geometry, entity, match):
    kind = (
        match[0]
        if isinstance(match, tuple)
        else FeatureKind(match.kind)
    )
    method = (
        match[1]
        if isinstance(match, tuple)
        else match.method
    )
    confidence = (
        match[2]
        if isinstance(match, tuple)
        else match.confidence
    )

    return _make_feature(
        geometry,
        entity,
        kind,
        confidence,
        method,
    )


def entity_to_feature(entity, match):
    return _feature_for_geometry(
        _entity_geometry(entity),
        entity,
        match,
    )


def parse_dxf(
    path,
    layers_path="data/config/layers.yaml",
    overrides=None,
):
    doc = ezdxf.readfile(path)
    entities = list(doc.modelspace())

    rules = load_layer_rules(layers_path)

    layer_names = sorted({
        entity.dxf.layer
        for entity in entities
    })

    matcher = LayerMatcher(overrides=overrides or {})
    matcher.fit(layer_names)

    resolved = {}

    for layer_name in layer_names:
        override = (overrides or {}).get(layer_name)

        if override is not None:
            try:
                resolved[layer_name] = (
                    FeatureKind(override),
                    "override",
                    1.0,
                )
                continue
            except (ValueError, TypeError):
                pass

        resolved[layer_name] = _resolve_kind(
            layer_name,
            rules,
            matcher,
        )

    result = ParseResult()
    counts = Counter()
    layer_entity_counts = Counter()

    urn_block_name = "\u0423\u0420\u041d\u0410__"
    maf_block_name = "*U476"

    maf_layer_name = "\u0414\u0412_\u0413\u041f_\u041f_\u041c\u0410\u0424"
    works_boundary_token = (
        "\u0413\u0420\u0410\u041d\u0418\u0426\u0410_\u0420\u0410\u0411\u041e\u0422"
    )

    for entity in entities:
        layer_name = entity.dxf.layer
        entity_type = entity.dxftype()

        kind, method, confidence = resolved[layer_name]

        layer_entity_counts[layer_name] += 1

        if (
            kind == FeatureKind.SITE_BOUNDARY
            and works_boundary_token in layer_name.upper()
        ):
            continue

        if (
            entity_type == "INSERT"
            and entity.dxf.name == urn_block_name
        ):
            counts[FeatureKind.BIN.value] += 1

            insertion = entity.dxf.insert

            result.features.append(
                Feature(
                    geom=Point(
                        float(insertion.x),
                        float(insertion.y),
                    ),
                    kind=FeatureKind.BIN,
                    source_layer=layer_name,
                    confidence=1.0,
                    match_method="dictionary",
                )
            )

            continue

        if (
            layer_name.upper() == maf_layer_name.upper()
            and entity_type == "INSERT"
            and entity.dxf.name == maf_block_name
        ):
            counts["MAF"] += 1

            geometry = _insert_geometry(entity)

            feature = _make_feature(
                geometry,
                layer_name,
                FeatureKind.MAF,
                1.0,
                "dictionary",
            )

            if feature is not None:
                result.features.append(feature)

            continue

        if kind is None:
            continue

        count_kind = (
            kind.value
            if isinstance(kind, FeatureKind)
            else str(kind)
        )

        counts[count_kind] += 1

        if kind == "ANNOTATION":
            continue

        if kind == FeatureKind.MAF:
            continue

        if entity_type == "INSERT":
            feature = _make_feature(
                Point(
                    float(entity.dxf.insert.x),
                    float(entity.dxf.insert.y),
                ),
                layer_name,
                kind,
                confidence,
                method,
            )
        else:
            feature = _make_feature(
                _entity_geometry(entity),
                layer_name,
                kind,
                confidence,
                method,
            )

        if feature is not None:
            result.features.append(feature)

    result.entity_counts_by_kind = dict(counts)

    result.unresolved_layers = []

    for layer_name in layer_names:
        kind, method, confidence = resolved[layer_name]

        if kind is not None:
            continue

        match = matcher.match(layer_name)

        result.unresolved_layers.append({
            "layer": layer_name,
            "entity_count": layer_entity_counts[layer_name],
            "tokens": list(match.tokens),
        })

    return result


def layer_to_kind(layer_name, layer_matcher=None):
    if isinstance(layer_matcher, list):
        for pattern, kind in layer_matcher:
            if pattern.search(layer_name):
                return kind

        return None

    if layer_matcher is None:
        layer_matcher = LayerMatcher()

    match = layer_matcher.match(layer_name)

    if match.method == "unknown":
        return None

    if match.kind == "ANNOTATION":
        return "ANNOTATION"

    try:
        return FeatureKind(match.kind)
    except ValueError:
        return None


def read_dxf(
    path,
    layers_path="data/config/layers.yaml",
    overrides=None,
):
    return parse_dxf(
        path,
        layers_path,
        overrides,
    ).features

