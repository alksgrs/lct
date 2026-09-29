import re

import yaml

from greenplan.models import FeatureKind


def load_layer_rules(path: str):
    with open(path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    result = []

    for item in data.get("layers", []):
        result.append(
            (
                re.compile(item["pattern"], re.IGNORECASE),
                FeatureKind(item["kind"])
            )
        )

    return result


def get_layer_kind(layer_name: str, rules):
    for pattern, kind in rules:
        if pattern.search(layer_name):
            return kind

    return FeatureKind.UNKNOWN