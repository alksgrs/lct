from dataclasses import dataclass, field

from shapely.geometry.base import BaseGeometry

from greenplan.constraints.constraints import get_site_boundary
from greenplan.models import Placement, Rejection, Rule
from greenplan.parser.dxf_parser import ParseResult, parse_dxf
from greenplan.planner.config import load_planting_config
from greenplan.planner.feature_index import FeatureIndex
from greenplan.planner.greening import Greening, load_greening_config, plan_greening
from greenplan.planner.planner import create_plan_with_rejections
from greenplan.rules.loader import load_rules
from greenplan.rules.rule_selector import get_rules

SPECIES_ORDER = ("tree", "shrub")


@dataclass
class Site:
    parsed: ParseResult
    boundary: BaseGeometry
    boundary_method: str
    boundary_outliers: int
    index: FeatureIndex


@dataclass
class PlanResult:
    site: Site
    rules: list[Rule]
    placements: list[Placement] = field(default_factory=list)
    rejections: list[Rejection] = field(default_factory=list)
    greening: Greening | None = None


def prepare_site(input_path: str, layers_path: str, overrides=None, boundary_layer=None) -> Site:
    parsed = parse_dxf(input_path, layers_path, overrides)
    boundary = get_site_boundary(parsed.features, boundary_layer=boundary_layer)
    polygon, method = boundary
    return Site(parsed=parsed, boundary=polygon, boundary_method=method,
                boundary_outliers=getattr(boundary, "outliers", 0),
                index=FeatureIndex(parsed.features))


def plan_species(site: Site, rules: list[Rule], config: dict, species_type: str, obstacles=None):
    if species_type not in config:
        raise ValueError(f"Нет настроек посадки для типа «{species_type}»")
    settings = config[species_type]
    return create_plan_with_rejections(
        area=site.boundary,
        species_type=species_type,
        rules=get_rules(rules, species_type),
        features=site.parsed.features,
        grid_spacing=settings["grid_spacing_m"],
        min_spacing=settings["min_spacing_m"],
        bin_offset=settings.get("bin_offset_m", 0) if species_type == "tree" else 0,
        obstacles=obstacles,
        obstacle_distance=settings.get("min_distance_to_trees_m", 0),
        index=site.index,
    )


def run_plan(input_path: str, rules_path: str, planting_path: str, layers_path: str,
             species=SPECIES_ORDER, overrides=None, boundary_layer=None) -> PlanResult:
    site = prepare_site(input_path, layers_path, overrides, boundary_layer)
    rules = load_rules(rules_path)
    config = load_planting_config(planting_path)
    result = PlanResult(site=site, rules=rules)
    trees = []
    for species_type in [s for s in SPECIES_ORDER if s in species]:
        placements, rejections = plan_species(
            site, rules, config, species_type,
            obstacles=trees if species_type == "shrub" else None,
        )
        if species_type == "tree":
            trees = [p.point for p in placements]
        if species_type == "shrub":
            result.greening, placements = plan_greening(
                site, rules, load_greening_config(planting_path), trees, placements,
            )
        result.placements.extend(placements)
        result.rejections.extend(rejections)
    return result


def build_plan(input_path: str, rules_path: str, planting_path: str, species_type: str,
               layers_path: str = "data/config/layers.yaml", warnings=None, unresolved_layers=None,
               overrides=None, boundary_layer=None, boundary_method=None):
    site = prepare_site(input_path, layers_path, overrides, boundary_layer)
    if unresolved_layers is not None:
        unresolved_layers.extend(site.parsed.unresolved_layers)
    if warnings is not None:
        warnings.extend(f"Неизвестный слой: {item['layer']}" for item in site.parsed.unresolved_layers)
    if boundary_method is not None:
        boundary_method.append(site.boundary_method)
    return plan_species(site, load_rules(rules_path), load_planting_config(planting_path), species_type)
