from pathlib import Path

import yaml

from greenplan.models import FeatureKind, Rule


def load_rules(path: str) -> list[Rule]:
    with open(path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    rules = []

    for item in data.get("rules", []):
        if not item.get("verified", False):
            continue

        rules.append(
            Rule(
                id=item["id"],
                object=FeatureKind(item["object"]),
                planting=item["planting"],
                min_distance_m=float(item["min_distance_m"]),
                act=item["act"],
                clause=item["clause"],
                verified=item["verified"]
            )
        )

    return rules