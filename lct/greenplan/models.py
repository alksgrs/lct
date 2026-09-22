from dataclasses import dataclass, field
from enum import Enum
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry


class FeatureKind(Enum):
    PIPE_WATER = "PIPE_WATER"
    PIPE_GAS = "PIPE_GAS"
    CABLE = "CABLE"
    BUILDING = "BUILDING"
    ROAD = "ROAD"
    POWERLINE = "POWERLINE"
    SITE_BOUNDARY = "SITE_BOUNDARY"
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


@dataclass
class Rejection:
    point: Point
    species_type: str
    violated: Rule