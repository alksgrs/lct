from shapely.strtree import STRtree

from greenplan.models import FeatureKind, Placement, Rejection, Rule
from greenplan.planner.feature_index import FeatureIndex
from greenplan.planner.hex_grid import DEFAULT_MAX_CANDIDATES, create_hex_grid
from greenplan.planner.point_checker import find_violation_detail
from greenplan.planner.rationale import check_point
from greenplan.planner.spacing import filter_by_spacing


def build_rationale(rules: list[Rule]) -> list[Rule]:
    return [rule for rule in rules if rule.verified]


def create_placement(allowed_zone, species_type: str, rules: list[Rule],
                     species: str | None = None) -> Placement:
    if allowed_zone.is_empty:
        raise ValueError("Allowed zone is empty")
    return Placement(point=allowed_zone.representative_point(), species_type=species_type,
                     species=species, rationale=rules)


def create_placements(allowed_zone, species_type: str, rules: list[Rule], grid_spacing: float,
                      min_spacing: float, features, species: str | None = None) -> list[Placement]:
    if allowed_zone.is_empty:
        return []
    index = FeatureIndex(features)
    points = filter_by_spacing(create_hex_grid(allowed_zone, grid_spacing, None), min_spacing)
    return [
        Placement(point=point, species_type=species_type, species=species,
                  rationale=build_rationale(rules), rule_checks=check_point(point, rules, index))
        for point in points
    ]


def create_plan(allowed_zone, species_type, rules, grid_spacing, min_spacing, features, species=None):
    return create_placements(allowed_zone, species_type, rules, grid_spacing, min_spacing, features, species)


def _occupied(point, index: FeatureIndex, bin_tree, bin_offset) -> bool:
    if index.contains(point, FeatureKind.MAF):
        return True
    if bin_tree is not None and len(bin_tree.query(point, predicate="dwithin", distance=bin_offset)):
        return True
    return False


def create_plan_with_rejections(area, species_type: str, rules: list[Rule], features,
                                grid_spacing: float, min_spacing: float, species: str | None = None,
                                bin_offset: float = 0, obstacles=None, obstacle_distance: float = 0,
                                max_candidates: int | None = DEFAULT_MAX_CANDIDATES,
                                index: FeatureIndex | None = None):
    index = index or FeatureIndex(features)
    bins = [f.geom for f in features if f.kind == FeatureKind.BIN]
    bin_tree = STRtree(bins) if bins and bin_offset > 0 else None
    obstacle_tree = STRtree(obstacles) if obstacles and obstacle_distance > 0 else None

    accepted = []
    rejections = []

    for point in create_hex_grid(area, grid_spacing, max_candidates):
        if _occupied(point, index, bin_tree, bin_offset):
            continue
        if obstacle_tree is not None and len(
            obstacle_tree.query(point, predicate="dwithin", distance=obstacle_distance)
        ):
            continue
        rule, distance = find_violation_detail(point, rules, index)
        if rule is not None:
            rejections.append(Rejection(point=point, species_type=species_type,
                                        violated=rule, distance_m=distance))
            continue
        accepted.append(point)

    rationale = build_rationale(rules)
    placements = [
        Placement(point=point, species_type=species_type, species=species,
                  rationale=rationale, rule_checks=check_point(point, rules, index))
        for point in filter_by_spacing(accepted, min_spacing)
    ]
    return placements, rejections
