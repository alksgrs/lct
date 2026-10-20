import pytest
from shapely.geometry import LineString, Point, Polygon

from greenplan.constraints.constraints import get_site_boundary
from greenplan.models import Feature, FeatureKind
from greenplan.parser.dxf_parser import ParseResult
from greenplan.pipeline import Site, plan_species
from greenplan.planner.feature_index import FeatureIndex
from greenplan.planner.hex_grid import AreaTooLarge, create_hex_grid
from greenplan.planner.config import load_planting_config
from greenplan.rules.loader import load_rules
from tests.paths import PLANTING, RULES


def make_site(features, boundary):
    return Site(parsed=ParseResult(features=features), boundary=boundary,
                boundary_method="layer", boundary_outliers=0, index=FeatureIndex(features))


def test_powerline_ban_zone_is_respected():
    boundary = Polygon([(0, 0), (40, 0), (40, 40), (0, 40)])
    line = LineString([(0, 20), (40, 20)])
    features = [
        Feature(geom=boundary, kind=FeatureKind.SITE_BOUNDARY, source_layer="ГРАНИЦА"),
        Feature(geom=line, kind=FeatureKind.POWERLINE_04KV, source_layer="ВЛ_НО"),
    ]
    site = make_site(features, boundary)
    rules = load_rules(RULES)
    config = load_planting_config(PLANTING)

    for species in ("tree", "shrub"):
        placements, rejections = plan_species(site, rules, config, species)
        assert placements
        assert all(line.distance(p.point) >= 2.0 for p in placements)
        assert any(r.violated.id == "powerline_04kv_ban" for r in rejections)


def test_not_regulated_rule_does_not_block_shrubs():
    boundary = Polygon([(0, 0), (20, 0), (20, 20), (0, 20)])
    gas = LineString([(0, 10), (20, 10)])
    features = [
        Feature(geom=boundary, kind=FeatureKind.SITE_BOUNDARY, source_layer="ГРАНИЦА"),
        Feature(geom=gas, kind=FeatureKind.PIPE_GAS, source_layer="ГАЗ"),
    ]
    site = make_site(features, boundary)
    rules = load_rules(RULES)
    config = load_planting_config(PLANTING)

    shrubs, _ = plan_species(site, rules, config, "shrub")
    trees, _ = plan_species(site, rules, config, "tree")
    assert min(gas.distance(p.point) for p in shrubs) < 1.5
    assert min(gas.distance(p.point) for p in trees) >= 1.5


def test_shrubs_keep_distance_from_trees():
    boundary = Polygon([(0, 0), (20, 0), (20, 20), (0, 20)])
    features = [Feature(geom=boundary, kind=FeatureKind.SITE_BOUNDARY, source_layer="ГРАНИЦА")]
    site = make_site(features, boundary)
    config = load_planting_config(PLANTING)
    trees, _ = plan_species(site, [], config, "tree")
    shrubs, _ = plan_species(site, [], config, "shrub", obstacles=[p.point for p in trees])
    limit = config["shrub"]["min_distance_to_trees_m"]
    for shrub in shrubs:
        assert min(shrub.point.distance(t.point) for t in trees) >= limit


def test_placement_explains_every_rule():
    boundary = Polygon([(0, 0), (20, 0), (20, 20), (0, 20)])
    road = LineString([(0, 0), (20, 0)])
    features = [
        Feature(geom=boundary, kind=FeatureKind.SITE_BOUNDARY, source_layer="ГРАНИЦА"),
        Feature(geom=road, kind=FeatureKind.ROAD, source_layer="БР"),
    ]
    site = make_site(features, boundary)
    rules = load_rules(RULES)
    placements, _ = plan_species(site, rules, load_planting_config(PLANTING), "tree")
    placement = placements[0]
    statuses = {check.rule.id: check.status for check in placement.rule_checks}
    assert statuses["road_tree"] == "allowed"
    assert statuses["gas_tree"] == "not_applicable"


def test_area_guard_stops_huge_grid():
    huge = Polygon([(0, 0), (10_000, 0), (10_000, 10_000), (0, 10_000)])
    with pytest.raises(AreaTooLarge):
        create_hex_grid(huge, 1.0)


def test_boundary_ignores_far_outliers():
    features = [
        Feature(geom=Point(x, y), kind=FeatureKind.LIGHTING, source_layer="ОПОРА")
        for x in range(0, 100, 10) for y in range(0, 100, 10)
    ]
    features.append(Feature(geom=Point(500_000, 500_000), kind=FeatureKind.LIGHTING, source_layer="ОПОРА"))
    boundary = get_site_boundary(features)
    polygon, method = boundary
    assert method == "convex_hull"
    assert boundary.outliers == 1
    assert polygon.area < 20_000


def test_long_drawing_falls_back_to_corridor():
    features = [
        Feature(geom=Point(x, 0), kind=FeatureKind.LIGHTING, source_layer="ОПОРА")
        for x in range(0, 3000, 30)
    ]
    features += [
        Feature(geom=Point(x, 400), kind=FeatureKind.LIGHTING, source_layer="ОПОРА")
        for x in range(0, 3000, 30)
    ]
    polygon, method = get_site_boundary(features)
    assert method == "corridor"
    assert not polygon.contains(Point(1500, 200))
    assert polygon.contains(Point(1500, 5))
