from dataclasses import dataclass, field
from math import pi

import numpy as np
import shapely
import yaml
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import linemerge, polylabel

from greenplan.models import FeatureKind, Placement, Rule, RuleKind
from greenplan.rules.rule_selector import get_rules


DEFAULTS = {
    "lawn": {
        "min_area_m2": 20.0,
        "offsets_m": {
            "ROAD": 0.5,
            "PAVEMENT": 0.3,
            "BUILDING": 1.0,
            "MAF": 0.3,
            "TRAM_TRACK": 2.0,
            "RETAINING_WALL": 0.5,
        },
    },
    "hedge": {
        "extra_offset_m": 0.3,
        "edge_gap_m": 0.2,
        "spacing_m": 2.0,
        "min_length_m": 8.0,
        "tree_gap_m": 2.0,
        "shrub_clear_m": 1.5,
    },
    "flowerbed": {
        "radius_m": 2.5,
        "min_lawn_area_m2": 400.0,
        "area_per_bed_m2": 4000.0,
        "tree_gap_m": 2.5,
        "bed_gap_m": 12.0,
        "edge_gap_m": 1.0,
        "utility_gap_m": 1.0,
        "max_count": 20,
    },
}


@dataclass
class Flowerbed:
    center: Point
    radius_m: float

    @property
    def shape(self) -> Polygon:
        return self.center.buffer(self.radius_m, quad_segs=12)


@dataclass
class Greening:
    lawn: BaseGeometry = field(default_factory=Polygon)
    hedges: list[LineString] = field(default_factory=list)
    flowerbeds: list[Flowerbed] = field(default_factory=list)
    shrubs_replaced: int = 0
    hedge_rules: list[Rule] = field(default_factory=list)
    settings: dict = field(default_factory=dict)

    @property
    def lawn_area_m2(self) -> float:
        return float(self.lawn.area) if not self.lawn.is_empty else 0.0

    @property
    def hedge_length_m(self) -> float:
        return float(sum(line.length for line in self.hedges))


def load_greening_config(path: str | None) -> dict:
    data = {}
    if path:
        with open(path, "r", encoding="utf-8") as file:
            data = (yaml.safe_load(file) or {}).get("greening", {}) or {}
    config = {}
    for section, defaults in DEFAULTS.items():
        values = dict(defaults)
        values.update(data.get(section, {}) or {})
        if section == "lawn":
            offsets = dict(defaults["offsets_m"])
            offsets.update((data.get("lawn", {}) or {}).get("offsets_m", {}) or {})
            values["offsets_m"] = {key: float(value) for key, value in offsets.items()}
        config[section] = {key: value if isinstance(value, dict) else float(value)
                           for key, value in values.items()}
    return config


def _polygons(geometry) -> list[Polygon]:
    if geometry is None or geometry.is_empty:
        return []
    if isinstance(geometry, Polygon):
        return [geometry]
    if isinstance(geometry, MultiPolygon):
        return list(geometry.geoms)
    return [part for part in getattr(geometry, "geoms", []) if isinstance(part, Polygon)]


def _lines(geometry) -> list[LineString]:
    if geometry is None or geometry.is_empty:
        return []
    if isinstance(geometry, LineString):
        return [geometry]
    if isinstance(geometry, MultiLineString):
        return list(geometry.geoms)
    result = []
    for part in getattr(geometry, "geoms", []):
        result.extend(_lines(part))
    return result


def lawn_zone(site, settings: dict) -> BaseGeometry:
    lawn_settings = settings["lawn"]
    area = site.boundary
    if area.is_empty:
        return Polygon()
    buffers = []
    for name, offset in lawn_settings["offsets_m"].items():
        try:
            kind = FeatureKind(name)
        except ValueError:
            continue
        geometries = site.index.geometries(kind)
        if geometries:
            buffers.extend(shapely.buffer(np.array(geometries, dtype=object), max(offset, 0.01), quad_segs=4))
    hard = shapely.union_all(buffers) if buffers else Polygon()
    lawn = area.difference(hard) if not hard.is_empty else area
    lawn = lawn.simplify(0.05, preserve_topology=True)
    pieces = [piece for piece in _polygons(lawn) if piece.area >= lawn_settings["min_area_m2"]]
    return MultiPolygon(pieces) if pieces else Polygon()


def shrub_forbidden_zone(site, rules: list[Rule], margin: float = 0.02) -> BaseGeometry:
    buffers = []
    for rule in get_rules(rules, "shrub"):
        if rule.kind == RuleKind.NOT_REGULATED or rule.limit_m <= 0:
            continue
        geometries = site.index.geometries(rule.object)
        if geometries:
            buffers.extend(shapely.buffer(np.array(geometries, dtype=object), rule.limit_m + margin, quad_segs=8))
    return shapely.union_all(buffers) if buffers else Polygon()


def hedge_lines(site, lawn, rules: list[Rule], trees: list[Point], settings: dict,
                forbidden=None) -> list[LineString]:
    hedge = settings["hedge"]
    if lawn.is_empty:
        return []
    shrub_rules = {rule.object: rule for rule in get_rules(rules, "shrub") if rule.kind == RuleKind.DISTANCE}
    inside = lawn.buffer(-hedge["edge_gap_m"], join_style="mitre")
    if inside.is_empty:
        return []
    blocked = [forbidden if forbidden is not None else shrub_forbidden_zone(site, rules)]
    if trees:
        blocked.append(shapely.union_all(shapely.buffer(np.array(trees, dtype=object), hedge["tree_gap_m"] + 0.03, quad_segs=8)))
    blocked = shapely.union_all([zone for zone in blocked if not zone.is_empty]) if blocked else Polygon()

    result, taken = [], Polygon()
    for kind in (FeatureKind.PAVEMENT, FeatureKind.ROAD):
        paths = site.index.geometries(kind)
        if not paths:
            continue
        rule = shrub_rules.get(kind)
        offset = (rule.limit_m if rule else 0.5) + hedge["extra_offset_m"]
        outline = shapely.union_all(shapely.buffer(np.array(paths, dtype=object), offset, quad_segs=8)).boundary
        outline = outline.simplify(0.05)
        candidate = outline.intersection(inside).difference(blocked)
        if not taken.is_empty:
            candidate = candidate.difference(taken)
        parts = _lines(candidate)
        if not parts:
            continue
        merged = _lines(linemerge(parts))
        kept = [line for line in merged if line.length >= hedge["min_length_m"]]
        result.extend(kept)
        if kept:
            taken = shapely.union_all([taken, *[line.buffer(hedge["spacing_m"]) for line in kept]])
    return result


UTILITY_KINDS = (
    FeatureKind.PIPE_WATER, FeatureKind.PIPE_SEWER, FeatureKind.PIPE_DRAINAGE,
    FeatureKind.PIPE_GAS, FeatureKind.PIPE_HEAT, FeatureKind.CABLE,
)


def place_flowerbeds(lawn, trees: list[Point], hedges: list[LineString], settings: dict,
                     forbidden=None, utilities=None) -> list[Flowerbed]:
    beds_cfg = settings["flowerbed"]
    radius = beds_cfg["radius_m"]
    obstacles = []
    if trees:
        obstacles.append(shapely.union_all(shapely.buffer(np.array(trees, dtype=object),
                                                          beds_cfg["tree_gap_m"] + radius + 0.05, quad_segs=8)))
    if hedges:
        obstacles.append(shapely.union_all([line.buffer(radius + 0.5) for line in hedges]))
    if forbidden is not None and not forbidden.is_empty:
        obstacles.append(forbidden.buffer(radius + 0.05, quad_segs=4))
    if utilities:
        obstacles.append(shapely.union_all(shapely.buffer(np.array(utilities, dtype=object),
                                                          radius + beds_cfg["utility_gap_m"] + 0.05, quad_segs=4)))
    blocked = shapely.union_all(obstacles) if obstacles else Polygon()

    beds = []
    for polygon in sorted(_polygons(lawn), key=lambda item: item.area, reverse=True):
        if polygon.area < beds_cfg["min_lawn_area_m2"] or len(beds) >= beds_cfg["max_count"]:
            break
        wanted = max(1, int(polygon.area // beds_cfg["area_per_bed_m2"]))
        region = polygon.buffer(-(radius + beds_cfg["edge_gap_m"])).difference(blocked)
        for _ in range(wanted):
            pieces = _polygons(region)
            if not pieces or len(beds) >= beds_cfg["max_count"]:
                break
            piece = max(pieces, key=lambda item: item.area)
            if piece.area < pi * 0.25:
                break
            center = polylabel(piece, tolerance=0.25)
            if not piece.buffer(1e-6).covers(center):
                center = piece.representative_point()
            beds.append(Flowerbed(center=center, radius_m=radius))
            region = region.difference(center.buffer(beds_cfg["bed_gap_m"] + 2 * radius))
    return beds


def plan_greening(site, rules: list[Rule], settings: dict, trees: list[Point],
                  shrubs: list[Placement]) -> tuple[Greening, list[Placement]]:
    lawn = lawn_zone(site, settings)
    forbidden = shrub_forbidden_zone(site, rules)
    hedges = hedge_lines(site, lawn, rules, trees, settings, forbidden)
    utilities = [geometry for kind in UTILITY_KINDS for geometry in site.index.geometries(kind)]
    beds = place_flowerbeds(lawn, trees, hedges, settings, forbidden, utilities)

    clear = settings["hedge"]["shrub_clear_m"]
    blockers = [line.buffer(clear) for line in hedges] + [bed.center.buffer(bed.radius_m + 0.5) for bed in beds]
    kept = shrubs
    if blockers and shrubs:
        zone = shapely.union_all(blockers)
        shapely.prepare(zone)
        xs = np.array([p.point.x for p in shrubs])
        ys = np.array([p.point.y for p in shrubs])
        inside = shapely.contains_xy(zone, xs, ys)
        kept = [placement for placement, hit in zip(shrubs, inside) if not hit]

    hedge_rules = [rule for rule in get_rules(rules, "shrub") if rule.kind != RuleKind.NOT_REGULATED]
    greening = Greening(lawn=lawn, hedges=hedges, flowerbeds=beds, shrubs_replaced=len(shrubs) - len(kept),
                        hedge_rules=hedge_rules, settings=settings)
    return greening, kept
