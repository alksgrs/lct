from greenplan.models import Placement, Rejection, Rule, RuleCheck, RuleKind
from greenplan.writer.geometry import geometry_to_json

OBJECT_LABELS = {
    "PIPE_WATER": "Водопровод",
    "PIPE_SEWER": "Канализация",
    "PIPE_DRAINAGE": "Дренаж, водосток",
    "PIPE_GAS": "Газопровод",
    "PIPE_HEAT": "Теплосеть",
    "CABLE": "Силовой кабель, связь",
    "BUILDING": "Наружная стена здания",
    "ROAD": "Край проезжей части",
    "PAVEMENT": "Край тротуара, дорожки",
    "LIGHTING": "Опора освещения",
    "POWERLINE": "Охранная зона ВЛ",
    "POWERLINE_04KV": "Охранная зона ВЛ до 1 кВ",
    "POWERLINE_6_10KV": "Охранная зона ВЛ 1–20 кВ",
    "POWERLINE_35KV": "Охранная зона ВЛ 35 кВ",
    "POWERLINE_110KV": "Охранная зона ВЛ 110 кВ",
    "TRAM_TRACK": "Ось трамвайных путей",
    "RETAINING_WALL": "Подпорная стенка",
    "SLOPE": "Подошва откоса, террасы",
    "SITE_BOUNDARY": "Граница участка",
    "MAF": "Малая архитектурная форма",
    "BIN": "Урна",
    "EXISTING_GREEN": "Газон, существующее озеленение",
}


def lower_first(text: str) -> str:
    if len(text) > 1 and text[1].isupper():
        return text
    return text[:1].lower() + text[1:]


def ru(value: float, digits: int | None = None) -> str:
    text = f"{value:.{digits}f}" if digits is not None else f"{value:g}"
    return text.replace(".", ",")


def _round(value):
    return None if value is None else round(float(value), 3)


def rule_to_dict(rule: Rule) -> dict:
    return {
        "rule_id": rule.id,
        "object": rule.object.value,
        "object_label": OBJECT_LABELS.get(rule.object.value, rule.object.value),
        "planting": rule.planting,
        "kind": rule.kind.value,
        "min_distance_m": rule.min_distance_m,
        "zone_m": rule.zone_m,
        "limit_m": rule.limit_m if rule.kind != RuleKind.NOT_REGULATED else None,
        "act": rule.act,
        "clause": rule.clause,
        "note": rule.note,
        "verified": rule.verified,
        "verified_by": rule.verified_by,
        "verified_at": rule.verified_at,
        "source_url": rule.source_url,
    }


def check_to_dict(check: RuleCheck) -> dict:
    data = rule_to_dict(check.rule)
    data.update({
        "status": check.status,
        "distance_m": _round(check.distance_m),
        "margin_m": _round(check.margin_m),
        "message": check.message,
    })
    return data


def placement_to_dict(placement: Placement) -> dict:
    return {
        "x": float(placement.point.x),
        "y": float(placement.point.y),
        "species_type": placement.species_type,
        "species": placement.species,
        "rationale": [rule_to_dict(rule) for rule in placement.rationale],
        "rule_checks": [check_to_dict(check) for check in placement.rule_checks],
    }


def rejection_to_dict(rejection: Rejection) -> dict:
    rule = rejection.violated
    distance = _round(rejection.distance_m)
    shortfall = None if distance is None else round(rule.limit_m - distance, 3)
    return {
        "x": float(rejection.point.x),
        "y": float(rejection.point.y),
        "species_type": rejection.species_type,
        "violated": rule_to_dict(rule),
        "distance_m": distance,
        "shortfall_m": shortfall,
        "reason": rejection_reason(rejection),
    }


def rejection_reason(rejection: Rejection) -> str:
    rule = rejection.violated
    label = lower_first(OBJECT_LABELS.get(rule.object.value, rule.object.value))
    if rule.kind == RuleKind.BAN:
        return f"Точка в охранной зоне {ru(rule.zone_m)} м: {label}"
    if rejection.distance_m is None:
        return f"Требуется не менее {ru(rule.limit_m)} м до объекта: {label}"
    return (f"До объекта «{label}» {ru(rejection.distance_m, 2)} м, "
            f"требуется не менее {ru(rule.limit_m)} м")


def greening_to_dict(greening) -> dict:
    if greening is None:
        return None
    lawn_settings = greening.settings.get("lawn", {})
    return {
        "lawn": geometry_to_json(greening.lawn, 0.05),
        "lawn_area_m2": round(greening.lawn_area_m2, 1),
        "lawn_offsets_m": dict(lawn_settings.get("offsets_m", {})),
        "hedges": [
            {
                "id": f"h{index}",
                "length_m": round(line.length, 2),
                "coordinates": [[round(x, 2), round(y, 2)] for x, y, *_ in line.coords],
            }
            for index, line in enumerate(greening.hedges)
        ],
        "hedge_length_m": round(greening.hedge_length_m, 1),
        "hedge_rule_ids": [rule.id for rule in greening.hedge_rules],
        "flowerbeds": [
            {"id": f"b{index}", "x": round(bed.center.x, 3), "y": round(bed.center.y, 3), "radius_m": bed.radius_m}
            for index, bed in enumerate(greening.flowerbeds)
        ],
        "shrubs_replaced": greening.shrubs_replaced,
    }
