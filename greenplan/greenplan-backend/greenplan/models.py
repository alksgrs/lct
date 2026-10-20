from dataclasses import dataclass, field
from enum import Enum

from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry


class FeatureKind(Enum):
    PIPE_WATER = "PIPE_WATER"
    PIPE_SEWER = "PIPE_SEWER"
    PIPE_DRAINAGE = "PIPE_DRAINAGE"
    PIPE_GAS = "PIPE_GAS"
    CABLE = "CABLE"
    PIPE_HEAT = "PIPE_HEAT"
    BUILDING = "BUILDING"
    ROAD = "ROAD"
    POWERLINE = "POWERLINE"
    LIGHTING = "LIGHTING"
    POWERLINE_04KV = "POWERLINE_04KV"
    POWERLINE_6_10KV = "POWERLINE_6_10KV"
    POWERLINE_35KV = "POWERLINE_35KV"
    POWERLINE_110KV = "POWERLINE_110KV"
    SITE_BOUNDARY = "SITE_BOUNDARY"
    MAF = "MAF"
    BIN = "BIN"
    EXISTING_GREEN = "EXISTING_GREEN"
    PAVEMENT = "PAVEMENT"
    TRAM_TRACK = "TRAM_TRACK"
    RETAINING_WALL = "RETAINING_WALL"
    SLOPE = "SLOPE"
    UNKNOWN = "UNKNOWN"


class RuleKind(str, Enum):
    DISTANCE = "distance"
    NOT_REGULATED = "not_regulated"
    BAN = "ban"


@dataclass
class Rule:
    id: str
    object: FeatureKind
    planting: str
    min_distance_m: float | None
    act: str
    clause: str
    verified: bool = False
    kind: RuleKind = RuleKind.DISTANCE
    zone_m: float | None = None
    note: str | None = None
    verified_by: str | None = None
    verified_at: str | None = None
    source_url: str | None = None

    @property
    def limit_m(self) -> float:
        if self.kind == RuleKind.BAN:
            return float(self.zone_m or 0)
        if self.kind == RuleKind.DISTANCE:
            return float(self.min_distance_m or 0)
        return 0.0


@dataclass
class RuleCheck:
    rule: Rule
    status: str
    distance_m: float | None = None
    message: str | None = None

    @property
    def margin_m(self) -> float | None:
        if self.distance_m is None or self.rule.kind == RuleKind.NOT_REGULATED:
            return None
        return self.distance_m - self.rule.limit_m


@dataclass
class Feature:
    geom: BaseGeometry
    kind: FeatureKind
    source_layer: str
    confidence: float = 1.0
    match_method: str = ""


@dataclass
class Placement:
    point: Point
    species_type: str
    species: str | None
    rationale: list[Rule] = field(default_factory=list)
    rule_checks: list[RuleCheck] = field(default_factory=list)


@dataclass
class Rejection:
    point: Point
    species_type: str
    violated: Rule
    distance_m: float | None = None
