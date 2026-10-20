import json

from greenplan.writer.serialize import placement_to_dict, rejection_to_dict, rule_to_dict


def _unique(items):
    seen, result = set(), []
    for item in items:
        key = item["rule_id"]
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def build_report(placements, input_path, species_type, rejections=None, warnings=None,
                 unresolved_layers=None, boundary_method=None, boundary_outliers=0, greening=None) -> dict:
    rejections = rejections or []
    placements_data = [placement_to_dict(p) for p in placements]
    rules = _unique(rule_to_dict(rule) for p in placements for rule in p.rationale)
    by_status = {}
    for placement in placements_data:
        for check in placement["rule_checks"]:
            by_status.setdefault(check["status"], []).append(check)

    report = {
        "input": input_path,
        "species_type": species_type,
        "placements_count": len(placements),
        "rejections_count": len(rejections),
        "rules": rules,
        "not_applicable_rules": _unique(by_status.get("not_applicable", [])),
        "not_regulated_rules": _unique(by_status.get("not_regulated", [])),
        "placements": placements_data,
        "rejections": [rejection_to_dict(r) for r in rejections],
        "unresolved_layers": unresolved_layers or [],
        "boundary_method": boundary_method,
        "boundary_outliers": boundary_outliers,
    }
    if greening is not None:
        report["greening"] = greening
    if warnings:
        report["warnings"] = warnings
    return report


def write_placements_json(placements, output_path: str, input_path: str, species_type: str,
                          rejections=None, warnings=None, unresolved_layers=None,
                          boundary_method=None, boundary_outliers=0, greening=None) -> None:
    report = build_report(placements, input_path, species_type, rejections, warnings,
                          unresolved_layers, boundary_method, boundary_outliers, greening)
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
