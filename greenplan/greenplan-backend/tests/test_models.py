from shapely.geometry import Point

from greenplan.models import Feature
from greenplan.models import FeatureKind
from greenplan.models import Placement
from greenplan.models import Rejection
from greenplan.models import Rule


rule = Rule(
    id="test_water_tree",
    object=FeatureKind.PIPE_WATER,
    planting="tree",
    min_distance_m=2.0,
    act="СП 42.13330.2016",
    clause="таблица 12.5",
    verified=True
)

feature = Feature(
    geom=Point(10, 20),
    kind=FeatureKind.PIPE_WATER,
    source_layer="water"
)

placement = Placement(
    point=Point(30, 40),
    species_type="tree",
    species=None,
    rationale=[rule]
)

rejection = Rejection(
    point=Point(20, 30),
    species_type="tree",
    violated=rule
)

print(feature)
print(placement)
print(rejection)