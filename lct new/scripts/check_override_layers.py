"""
Диагностика: дают ли слои, назначенные через --override, фичи, и как далеко
от них ближайшие посадки из готового out.json.

Использование (из корня проекта):
    python scripts/check_override_layers.py файл.dxf out.json СЛОЙ [СЛОЙ ...]
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shapely.geometry import Point

from greenplan.models import FeatureKind
from greenplan.parser.dxf_parser import parse_dxf


def min_distance(points, features):
    if not points or not features:
        return None
    return min(
        point.distance(feature.geom)
        for point in points
        for feature in features
    )


def bounds_of(features):
    boxes = [feature.geom.bounds for feature in features]
    if not boxes:
        return None
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def bounds_of_points(points):
    if not points:
        return None
    return (
        min(p.x for p in points),
        min(p.y for p in points),
        max(p.x for p in points),
        max(p.y for p in points),
    )


def fmt(bounds):
    if bounds is None:
        return "—"
    return "x {:.1f}..{:.1f}, y {:.1f}..{:.1f}".format(
        bounds[0], bounds[2], bounds[1], bounds[3]
    )


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)

    dxf_path, report_path, *layers = sys.argv[1:]

    with open(report_path, encoding="utf-8") as file:
        report = json.load(file)
    points = [Point(p["x"], p["y"]) for p in report["placements"]]
    print(f"посадок в отчёте: {len(points)}")

    parsed = parse_dxf(
        dxf_path,
        overrides={layer: "ROAD" for layer in layers}
    )
    roads = [f for f in parsed.features if f.kind == FeatureKind.ROAD]
    others = [f for f in roads if f.source_layer not in layers]
    print(f"ROAD-фич всего: {len(roads)}, из них вне указанных слоёв: {len(others)}\n")

    for layer in layers:
        layer_features = [f for f in roads if f.source_layer == layer]
        types = Counter(f.geom.geom_type for f in layer_features)
        distance = min_distance(points, layer_features)
        print(f"{layer}: фич {len(layer_features)}, типы {dict(types)}")
        if layer_features:
            print(f"   min расстояние до посадки: {distance:.2f}")
            print(f"   границы: {fmt(bounds_of(layer_features))}")

    print()
    site = [f for f in parsed.features if f.kind == FeatureKind.SITE_BOUNDARY]
    print(f"границы участка (SITE_BOUNDARY, {len(site)} фич): {fmt(bounds_of(site))}")
    print(f"границы всех посадок: {fmt(bounds_of_points(points))}")
    distance = min_distance(points, others)
    if distance is not None:
        print(f"остальные ROAD-фичи: min расстояние до посадки {distance:.2f}")

    close = [
        round(point.distance(feature.geom), 2)
        for point in points
        for feature in roads
        if feature.source_layer in layers and point.distance(feature.geom) < 2.0
    ]
    print(f"посадок ближе 2.0 к указанным слоям: {len(close)}")


if __name__ == "__main__":
    main()

