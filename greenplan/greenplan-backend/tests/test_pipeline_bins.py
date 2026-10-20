from shapely.geometry import Point, Polygon

from greenplan.models import Feature, FeatureKind
from greenplan.parser.dxf_parser import ParseResult
from greenplan.pipeline import Site, plan_species
from greenplan.planner.feature_index import FeatureIndex


def test_tree_plan_keeps_clear_of_bins():
    site_polygon = Polygon([(0, 0), (20, 0), (20, 20), (0, 20)])
    features = [
        Feature(geom=site_polygon, kind=FeatureKind.SITE_BOUNDARY, source_layer="TEST"),
        Feature(geom=Point(10, 10), kind=FeatureKind.BIN, source_layer="TEST"),
    ]
    site = Site(parsed=ParseResult(features=features), boundary=site_polygon,
                boundary_method="layer", boundary_outliers=0, index=FeatureIndex(features))
    config = {"tree": {"grid_spacing_m": 0.5, "min_spacing_m": 0.5, "bin_offset_m": 0.1}}

    placements, _ = plan_species(site, [], config, "tree")

    assert placements
    assert all(p.point.distance(Point(10, 10)) >= 0.1 for p in placements)
