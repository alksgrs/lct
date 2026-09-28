import json


def write_placements_json(
    placements,
    output_path: str,
    input_path: str,
    species_type: str,
    rejections=None
) -> None:
    if rejections is None:
        rejections = []

    placements_data = []

    for placement in placements:
        item = {
            "x": placement.point.x,
            "y": placement.point.y,
            "species_type": placement.species_type,
            "species": placement.species,
            "rationale": [],
            "rule_checks": []
        }

        for rule in placement.rationale:
            item["rationale"].append({
                "rule_id": rule.id,
                "object": rule.object.value,
                "planting": rule.planting,
                "min_distance_m": rule.min_distance_m,
                "act": rule.act,
                "clause": rule.clause
            })

        for check in placement.rule_checks:
            item["rule_checks"].append({
                "rule_id": check.rule.id,
                "status": check.status,
                "distance_m": check.distance_m
            })

        placements_data.append(item)

    rejections_data = []

    for rejection in rejections:
        rejections_data.append({
            "x": rejection.point.x,
            "y": rejection.point.y,
            "species_type": rejection.species_type,
            "violated": {
                "rule_id": rejection.violated.id,
                "object": rejection.violated.object.value,
                "planting": rejection.violated.planting,
                "min_distance_m": rejection.violated.min_distance_m,
                "act": rejection.violated.act,
                "clause": rejection.violated.clause
            }
        })

    rules_data = []

    for placement in placements:
        for rule in placement.rationale:
            rule_data = {
                "rule_id": rule.id,
                "object": rule.object.value,
                "planting": rule.planting,
                "min_distance_m": rule.min_distance_m,
                "act": rule.act,
                "clause": rule.clause
            }

            if rule_data not in rules_data:
                rules_data.append(rule_data)

    data = {
        "input": input_path,
        "species_type": species_type,
        "placements_count": len(placements),
        "rejections_count": len(rejections),
        "rules": rules_data,
        "placements": placements_data,
        "rejections": rejections_data
    }

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )

