import ezdxf
import pytest
from shapely.geometry import LineString, Point, Polygon

from greenplan.models import Feature, FeatureKind, Placement
from greenplan.parser.dxf_parser import ParseResult
from greenplan.pipeline import Site
from greenplan.planner.feature_index import FeatureIndex
from greenplan.planner.greening import (
    hedge_lines,
    lawn_zone,
    load_greening_config,
    place_flowerbeds,
    plan_greening,
)
from greenplan.rules.loader import load_rules
from greenplan.writer.dxf_writer import write_plan
from greenplan.writer.serialize import greening_to_dict
from tests.paths import PLANTING, RULES, TEST_DXF


def make_site(features, boundary):
    return Site(parsed=ParseResult(features=features), boundary=boundary,
                boundary_method="layer", boundary_outliers=0, index=FeatureIndex(features))


@pytest.fixture(scope="module")
def settings():
    return load_greening_config(PLANTING)


@pytest.fixture(scope="module")
def rules():
    return load_rules(RULES)


@pytest.fixture
def square():
    boundary = Polygon([(0, 0), (60, 0), (60, 60), (0, 60)])
    road = Polygon([(0, 26), (60, 26), (60, 34), (0, 34)])
    path = LineString([(10, 5), (10, 20)])
    heat = LineString([(40, 0), (40, 60)])
    features = [
        Feature(geom=boundary, kind=FeatureKind.SITE_BOUNDARY, source_layer="ГРАНИЦА"),
        Feature(geom=road, kind=FeatureKind.ROAD, source_layer="АБ_ПЧ"),
        Feature(geom=path, kind=FeatureKind.PAVEMENT, source_layer="ДОРОЖКА"),
        Feature(geom=heat, kind=FeatureKind.PIPE_HEAT, source_layer="ТС"),
    ]
    return make_site(features, boundary), road, path, heat


def test_config_has_design_offsets(settings):
    assert settings["lawn"]["offsets_m"]["ROAD"] == 0.5
    assert settings["hedge"]["min_length_m"] > 0
    assert settings["flowerbed"]["radius_m"] > 0


def test_lawn_avoids_hard_surfaces(square, settings):
    site, road, path, _ = square
    lawn = lawn_zone(site, settings)
    assert lawn.area > 2500
    assert lawn.intersection(road).area == pytest.approx(0, abs=1e-6)
    assert lawn.distance(road) >= settings["lawn"]["offsets_m"]["ROAD"] - 0.06
    assert lawn.distance(path) >= settings["lawn"]["offsets_m"]["PAVEMENT"] - 0.06


def test_hedges_follow_paths_and_respect_shrub_norms(square, settings, rules):
    site, road, path, heat = square
    lawn = lawn_zone(site, settings)
    hedges = hedge_lines(site, lawn, rules, [], settings)
    assert hedges
    for line in hedges:
        assert line.length >= settings["hedge"]["min_length_m"]
        assert line.distance(road) >= 1.0
        assert line.distance(path) >= 0.5
        assert line.distance(heat) >= 1.0
        assert min(line.distance(road), line.distance(path)) <= 1.0 + settings["hedge"]["extra_offset_m"] + 0.1


def test_hedges_keep_clear_of_trees(square, settings, rules):
    site, *_ = square
    lawn = lawn_zone(site, settings)
    trees = [Point(30, 24.7), Point(20, 35.3)]
    for line in hedge_lines(site, lawn, rules, trees, settings):
        assert min(line.distance(tree) for tree in trees) >= settings["hedge"]["tree_gap_m"] - 1e-6


def test_flowerbeds_inside_lawn_and_away_from_trees(square, settings, rules):
    site, *_ = square
    lawn = lawn_zone(site, settings)
    trees = [Point(15, 45), Point(50, 10)]
    beds = place_flowerbeds(lawn, trees, [], settings)
    assert beds
    for bed in beds:
        assert lawn.buffer(1e-6).covers(bed.shape)
        assert min(bed.center.distance(tree) for tree in trees) >= settings["flowerbed"]["tree_gap_m"] + bed.radius_m - 1e-6


def test_plan_greening_replaces_shrubs_under_hedges(square, settings, rules):
    site, *_ = square
    shrubs = [Placement(point=Point(x, y), species_type="shrub", species=None)
              for x in range(2, 60, 3) for y in range(2, 60, 3)]
    greening, kept = plan_greening(site, rules, settings, [], shrubs)
    assert greening.lawn_area_m2 > 0
    assert greening.hedges
    assert 0 < len(kept) < len(shrubs)
    assert greening.shrubs_replaced == len(shrubs) - len(kept)
    for placement in kept:
        assert min(line.distance(placement.point) for line in greening.hedges) >= settings["hedge"]["shrub_clear_m"] - 1e-6


def test_greening_goes_to_dxf_layers(square, settings, rules, tmp_path):
    site, *_ = square
    greening, _ = plan_greening(site, rules, settings, [], [])
    data = greening_to_dict(greening)
    output = tmp_path / "out.dxf"
    write_plan(TEST_DXF, str(output), [], data)
    doc = ezdxf.readfile(output)
    layers = {entity.dxf.layer for entity in doc.modelspace()}
    assert {"PLANTING_LAWN", "PLANTING_HEDGES"} <= layers
    if data["flowerbeds"]:
        assert "PLANTING_FLOWERBEDS" in layers
    hatches = [e for e in doc.modelspace() if e.dxftype() == "HATCH" and e.dxf.layer == "PLANTING_LAWN"]
    assert hatches and hatches[0].dxf.pattern_name == "GRASS"


def test_flowerbeds_keep_shrub_norms(square, settings, rules):
    site, road, path, heat = square
    greening, _ = plan_greening(site, rules, settings, [], [])
    assert greening.flowerbeds
    for bed in greening.flowerbeds:
        assert bed.shape.distance(heat) >= 1.0 - 1e-6
        assert bed.shape.distance(road) >= 1.0 - 1e-6


def test_flowerbeds_stay_off_unregulated_pipes(settings, rules):
    boundary = Polygon([(0, 0), (60, 0), (60, 60), (0, 60)])
    water = LineString([(0, 30), (60, 30)])
    features = [
        Feature(geom=boundary, kind=FeatureKind.SITE_BOUNDARY, source_layer="ГРАНИЦА"),
        Feature(geom=water, kind=FeatureKind.PIPE_WATER, source_layer="В1"),
    ]
    greening, _ = plan_greening(make_site(features, boundary), rules, settings, [], [])
    assert greening.flowerbeds
    for bed in greening.flowerbeds:
        assert bed.shape.distance(water) >= settings["flowerbed"]["utility_gap_m"] - 1e-6
