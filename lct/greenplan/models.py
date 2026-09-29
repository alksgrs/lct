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
    UNKNOWN = "UNKNOWN"


@dataclass
class Rule:
    id: str
    object: FeatureKind
    planting: str
    min_distance_m: float
    act: str
    clause: str
    verified: bool = False


@dataclass
class RuleCheck:
    rule: Rule
    status: str
    distance_m: float | None = None
    message: str | None = None


@dataclass
class Feature:
    geom: BaseGeometry
    kind: FeatureKind
    source_layer: str
    confidence: float = 1.0


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