import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import ezdxf
import yaml
from ezdxf import path as ezpath
from ezdxf.disassemble import recursive_decompose
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import polygonize, unary_union

from greenplan.config.layer_matcher import LayerMatcher
from greenplan.models import Feature, FeatureKind

logging.getLogger("ezdxf").setLevel(logging.ERROR)

FLATTEN_TOLERANCE = 0.05

POINT_LIKE = {
    FeatureKind.LIGHTING,
    FeatureKind.BIN,
    FeatureKind.POWERLINE,
    FeatureKind.POWERLINE_04KV,
    FeatureKind.POWERLINE_6_10KV,
    FeatureKind.POWERLINE_35KV,
    FeatureKind.POWERLINE_110KV,
}

POWERLINE_KINDS = POINT_LIKE - {FeatureKind.LIGHTING, FeatureKind.BIN}

VOLTAGE_PATTERNS = (
    (re.compile(r"110\s*КВ|ВЛ[_\s-]*110"), FeatureKind.POWERLINE_110KV),
    (re.compile(r"35\s*КВ|ВЛ[_\s-]*35"), FeatureKind.POWERLINE_35KV),
    (re.compile(r"(?<!\d)(6|10|20)\s*КВ|ВЛ[_\s-]*(6|10|20)(?!\d)"), FeatureKind.POWERLINE_6_10KV),
    (re.compile(r"0[.,]4\s*КВ|04\s*КВ|(^|_)НО($|_)|НАРУЖН"), FeatureKind.POWERLINE_04KV),
)

BIN_BLOCK = re.compile(r"УРН", re.IGNORECASE)

BLOCK_KINDS = {"MAF", "BIN", "LIGHTING", "BUILDING"}

TEXT_ONLY = {"TEXT", "MTEXT", "DIMENSION", "LEADER", "MULTILEADER", "ATTDEF", "TOLERANCE", "IMAGE", "WIPEOUT", "OLE2FRAME", "VIEWPORT"}


@dataclass
class ParseResult:
    features: list[Feature] = field(default_factory=list)
    unresolved_layers: list[dict] = field(default_factory=list)
    entity_counts_by_kind: dict[str, int] = field(default_factory=dict)
    layers: list[dict] = field(default_factory=list)


def _points_from_path(entity):
    if entity.dxftype() == "LWPOLYLINE":
        return [(float(p[0]), float(p[1])) for p in entity.get_points()]
    if entity.dxftype() == "POLYLINE":
        return [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in entity.vertices]
    return []


def lwpolyline_to_geometry(entity):
    points = _points_from_path(entity)
    if len(points) < 2:
        return None
    closed = entity.closed if entity.dxftype() == "LWPOLYLINE" else entity.is_closed
    if closed and len(points) >= 3:
        polygon = Polygon(points)
        if polygon.is_valid and not polygon.is_empty:
            return polygon
        fixed = polygon.buffer(0)
        return None if fixed.is_empty else fixed
    return LineString(points)


def _flattened(entity):
    try:
        points = [(float(v.x), float(v.y)) for v in entity.flattening(FLATTEN_TOLERANCE)]
    except Exception:
        return None
    return LineString(points) if len(points) >= 2 else None


def _hatch_geometry(entity):
    polygons = []
    try:
        paths = ezpath.from_hatch(entity)
    except Exception:
        return None
    for item in paths:
        try:
            points = [(float(v.x), float(v.y)) for v in item.flattening(FLATTEN_TOLERANCE)]
        except Exception:
            continue
        if len(points) < 3:
            continue
        polygon = Polygon(points).buffer(0)
        if not polygon.is_empty and polygon.area > 0:
            polygons.append(polygon)
    if not polygons:
        return None
    return unary_union(polygons)


def _entity_geometry(entity):
    kind = entity.dxftype()
    if kind in ("LWPOLYLINE", "POLYLINE"):
        return lwpolyline_to_geometry(entity)
    if kind == "LINE":
        start, end = entity.dxf.start, entity.dxf.end
        return LineString([(float(start.x), float(start.y)), (float(end.x), float(end.y))])
    if kind == "POINT":
        location = entity.dxf.location
        return Point(float(location.x), float(location.y))
    if kind == "CIRCLE":
        center = entity.dxf.center
        return Point(float(center.x), float(center.y)).buffer(float(entity.dxf.radius))
    if kind in ("ARC", "ELLIPSE", "SPLINE"):
        return _flattened(entity)
    if kind == "HATCH":
        return _hatch_geometry(entity)
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

    polygons = [g for g in geometries if g.geom_type in ("Polygon", "MultiPolygon")]
    if polygons:
        merged = unary_union(polygons)
        if merged.geom_type == "MultiPolygon":
            return max(merged.geoms, key=lambda polygon: polygon.area)
        return merged

    lines = [g for g in geometries if g.geom_type in ("LineString", "MultiLineString")]
    if lines:
        merged = unary_union(lines)
        closed = list(polygonize(merged))
        if closed:
            return max(closed, key=lambda polygon: polygon.area)
        return merged
    return None


def load_layer_rules(layers_path):
    with Path(layers_path).open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
    rules = []
    for item in config.get("layers", []):
        name = item["kind"]
        if not hasattr(FeatureKind, name):
            raise ValueError(f"Неизвестный тип слоя в конфигурации: {name}")
        rules.append((re.compile(item["pattern"], re.IGNORECASE), FeatureKind[name]))
    return rules


def _refine_powerline(kind, layer_name):
    if kind != FeatureKind.POWERLINE:
        return kind
    upper = layer_name.upper()
    for pattern, refined in VOLTAGE_PATTERNS:
        if pattern.search(upper):
            return refined
    return kind


def _resolve_kind(layer_name, rules, matcher):
    for pattern, kind in rules:
        if pattern.search(layer_name):
            return _refine_powerline(kind, layer_name), "config", 1.0

    match = matcher.match(layer_name)
    if match.method == "unknown":
        return None, "unknown", 0.0
    if match.kind == "ANNOTATION":
        return "ANNOTATION", match.method, match.confidence
    try:
        return _refine_powerline(FeatureKind(match.kind), layer_name), match.method, match.confidence
    except ValueError:
        return None, "unknown", 0.0


def _block_kind(name, matcher):
    if not name or name.startswith("*"):
        return None
    match = matcher.match(name)
    if match.method in ("dictionary", "fuzzy") and match.kind in BLOCK_KINDS:
        return FeatureKind(match.kind)
    return None


def _make_feature(geometry, layer_name, kind, confidence, method):
    if geometry is None or geometry.is_empty or not isinstance(kind, FeatureKind):
        return None
    return Feature(geom=geometry, kind=kind, source_layer=layer_name,
                   confidence=confidence, match_method=method)


def _insertion_point(entity):
    insert = entity.dxf.insert
    return Point(float(insert.x), float(insert.y))


def _feature_geometry(entity, kind):
    if entity.dxftype() == "INSERT":
        if kind in POINT_LIKE:
            return _insertion_point(entity)
        return _insert_geometry(entity) or _insertion_point(entity)
    return _entity_geometry(entity)


def _final_kind(kind, geometry):
    if kind == FeatureKind.LIGHTING and geometry.geom_type in ("LineString", "MultiLineString"):
        return FeatureKind.CABLE
    return kind


def parse_dxf(path, layers_path="data/config/layers.yaml", overrides=None):
    overrides = overrides or {}
    doc = ezdxf.readfile(path)
    entities = list(doc.modelspace())
    rules = load_layer_rules(layers_path)
    layer_names = sorted({entity.dxf.layer for entity in entities})

    matcher = LayerMatcher(overrides=overrides)
    matcher.fit(layer_names)

    types_by_layer = defaultdict(set)
    for entity in entities:
        types_by_layer[entity.dxf.layer].add(entity.dxftype())

    resolved = {}
    for layer_name in layer_names:
        override = overrides.get(layer_name)
        if override == "ANNOTATION":
            resolved[layer_name] = ("ANNOTATION", "override", 1.0)
            continue
        if override is not None:
            try:
                resolved[layer_name] = (FeatureKind(override), "override", 1.0)
                continue
            except ValueError:
                pass
        kind = _resolve_kind(layer_name, rules, matcher)
        if kind[0] is None and types_by_layer[layer_name] <= TEXT_ONLY:
            kind = ("ANNOTATION", "content", 1.0)
        resolved[layer_name] = kind

    result = ParseResult()
    counts = Counter()
    entities_per_layer = Counter()
    types_per_layer = defaultdict(Counter)
    typed_by_block = Counter()

    for entity in entities:
        layer_name = entity.dxf.layer
        entity_type = entity.dxftype()
        entities_per_layer[layer_name] += 1
        types_per_layer[layer_name][entity_type] += 1
        kind, method, confidence = resolved[layer_name]

        if entity_type == "INSERT" and BIN_BLOCK.search(entity.dxf.name or ""):
            counts[FeatureKind.BIN.value] += 1
            result.features.append(Feature(geom=_insertion_point(entity), kind=FeatureKind.BIN,
                                           source_layer=layer_name, confidence=1.0,
                                           match_method="block"))
            continue

        if kind is None and entity_type == "INSERT":
            block_kind = _block_kind(entity.dxf.name, matcher)
            if block_kind is not None:
                kind, method, confidence = block_kind, "block", 0.8
                typed_by_block[layer_name] += 1
        if kind is None:
            continue
        counts[kind.value if isinstance(kind, FeatureKind) else str(kind)] += 1
        if kind == "ANNOTATION":
            continue
        if kind == FeatureKind.MAF and entity_type != "INSERT":
            continue

        try:
            geometry = _feature_geometry(entity, kind)
        except Exception:
            geometry = None
        if geometry is None or geometry.is_empty:
            continue
        if kind == FeatureKind.MAF and geometry.geom_type != "Polygon":
            continue

        feature = _make_feature(geometry, layer_name, _final_kind(kind, geometry), confidence, method)
        if feature is not None:
            result.features.append(feature)

    result.entity_counts_by_kind = dict(counts)

    for layer_name in layer_names:
        kind, method, confidence = resolved[layer_name]
        kind_name = kind.value if isinstance(kind, FeatureKind) else kind
        record = {
            "layer": layer_name,
            "kind": kind_name,
            "method": method,
            "entity_count": entities_per_layer[layer_name],
            "entity_types": dict(types_per_layer[layer_name]),
            "typed_by_block": typed_by_block[layer_name],
        }
        result.layers.append(record)
        if kind is None:
            result.unresolved_layers.append({
                "layer": layer_name,
                "entity_count": entities_per_layer[layer_name],
                "tokens": list(matcher.match(layer_name).tokens),
            })

    return result


def layer_to_kind(layer_name, layer_matcher=None):
    if isinstance(layer_matcher, list):
        for pattern, kind in layer_matcher:
            if pattern.search(layer_name):
                return kind
        return None
    match = (layer_matcher or LayerMatcher()).match(layer_name)
    if match.method == "unknown":
        return None
    if match.kind == "ANNOTATION":
        return "ANNOTATION"
    try:
        return FeatureKind(match.kind)
    except ValueError:
        return None


def read_dxf(path, layers_path="data/config/layers.yaml", overrides=None):
    return parse_dxf(path, layers_path, overrides).features
