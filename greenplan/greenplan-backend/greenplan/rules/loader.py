import yaml

from greenplan.models import FeatureKind, Rule, RuleKind


def _number(value):
    return None if value is None else float(value)


def load_rules(path: str) -> list[Rule]:
    with open(path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    rules = []

    for item in data.get("rules", []):
        if not item.get("verified", False):
            continue

        kind = RuleKind(item.get("kind", RuleKind.DISTANCE.value))
        min_distance = _number(item.get("min_distance_m"))
        zone = _number(item.get("zone_m"))

        if kind == RuleKind.DISTANCE and min_distance is None:
            raise ValueError(f"Правило {item['id']}: для kind=distance нужно min_distance_m")
        if kind == RuleKind.BAN and zone is None:
            raise ValueError(f"Правило {item['id']}: для kind=ban нужно zone_m")
        if not item.get("act") or not item.get("clause"):
            raise ValueError(f"Правило {item['id']}: включённое правило без act или clause")

        rules.append(
            Rule(
                id=item["id"],
                object=FeatureKind(item["object"]),
                planting=item["planting"],
                min_distance_m=min_distance,
                act=item["act"],
                clause=item["clause"],
                verified=True,
                kind=kind,
                zone_m=zone,
                note=item.get("note"),
                verified_by=item.get("verified_by"),
                verified_at=str(item["verified_at"]) if item.get("verified_at") else None,
                source_url=item.get("source_url"),
            )
        )

    return rules


def load_pending_rules(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    return [
        {
            "rule_id": item["id"],
            "object": item["object"],
            "planting": item["planting"],
            "kind": item.get("kind", RuleKind.DISTANCE.value),
            "min_distance_m": _number(item.get("min_distance_m")),
            "zone_m": _number(item.get("zone_m")),
            "act": item.get("act"),
            "clause": item.get("clause"),
            "note": item.get("note"),
            "source_url": item.get("source_url"),
        }
        for item in data.get("rules", [])
        if not item.get("verified", False)
    ]
