import pytest
from shapely import STRtree

from greenplan.models import FeatureKind, RuleKind
from greenplan.pipeline import run_plan
from tests.paths import GENPLAN, KHARKOVSKAYA, LAYERS, PARKOVAYA, PLANTING, RULES

SAMPLES = [GENPLAN, PARKOVAYA, KHARKOVSKAYA]


@pytest.fixture(scope="module", params=SAMPLES, ids=["genplan", "parkovaya", "kharkovskaya"])
def plan(request):
    return run_plan(request.param, RULES, PLANTING, LAYERS)


def test_sample_produces_trees_and_shrubs(plan):
    species = {p.species_type for p in plan.placements}
    assert species == {"tree", "shrub"}
    assert plan.site.boundary.area < 250_000


def test_sample_has_no_norm_violations(plan):
    features = plan.site.parsed.features
    by_kind = {}
    for feature in features:
        by_kind.setdefault(feature.kind, []).append(feature.geom)
    trees = {kind: (STRtree(geoms), geoms) for kind, geoms in by_kind.items()}

    for rule in plan.rules:
        if rule.kind == RuleKind.NOT_REGULATED or rule.object not in trees:
            continue
        tree, geoms = trees[rule.object]
        targets = [p for p in plan.placements if rule.planting in (p.species_type, "any")]
        for placement in targets:
            nearest = geoms[tree.nearest(placement.point)]
            assert nearest.distance(placement.point) >= rule.limit_m - 1e-6, (rule.id, placement.point)


def test_sample_placements_are_inside_boundary(plan):
    boundary = plan.site.boundary.buffer(1e-6)
    assert all(boundary.covers(p.point) for p in plan.placements)


def test_sample_greening_respects_norms(plan):
    greening = plan.greening
    assert greening is not None
    assert greening.lawn_area_m2 > 0

    features = plan.site.parsed.features
    hard = [f.geom for f in features if f.kind in (FeatureKind.ROAD, FeatureKind.PAVEMENT, FeatureKind.BUILDING)
            and f.geom.geom_type in ("Polygon", "MultiPolygon")]
    assert sum(greening.lawn.intersection(geom).area for geom in hard) == pytest.approx(0, abs=0.01)

    by_kind = {}
    for feature in features:
        by_kind.setdefault(feature.kind, []).append(feature.geom)
    for rule in plan.rules:
        if rule.kind == RuleKind.NOT_REGULATED or rule.planting not in ("shrub", "any"):
            continue
        geoms = by_kind.get(rule.object)
        if not geoms:
            continue
        tree = STRtree(geoms)
        for line in greening.hedges:
            steps = int(line.length / 0.5) + 1
            for step in range(steps + 1):
                point = line.interpolate(min(step * 0.5, line.length))
                assert geoms[tree.nearest(point)].distance(point) >= rule.limit_m - 1e-6, (rule.id, point)

    for bed in greening.flowerbeds:
        assert greening.lawn.buffer(1e-6).covers(bed.center)
    for rule in plan.rules:
        if rule.kind == RuleKind.NOT_REGULATED or rule.planting not in ("shrub", "any"):
            continue
        for geom in by_kind.get(rule.object, []):
            for bed in greening.flowerbeds:
                assert bed.shape.distance(geom) >= rule.limit_m - 0.02, (rule.id, bed.center)
