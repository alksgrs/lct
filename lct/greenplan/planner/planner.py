from greenplan.models import Placement, Rule
from greenplan.planner.hex_grid import create_hex_grid
from greenplan.planner.spacing import filter_by_spacing
from greenplan.planner.rationale import check_rule
from greenplan.models import Placement, Rejection, Rule
from greenplan.planner.point_checker import find_violation


def create_placement(
    allowed_zone,
    species_type: str,
    rules: list[Rule],
    species: str | None = None
) -> Placement:
    if allowed_zone.is_empty:
        raise ValueError("Allowed zone is empty")

    point = allowed_zone.representative_point()

    return Placement(
        point=point,
        species_type=species_type,
        species=species,
        rationale=rules
    )


def create_placements(
    allowed_zone,
    species_type: str,
    rules: list[Rule],
    grid_spacing: float,
    min_spacing: float,
    features,
    species: str | None = None
) -> list[Placement]:
    if allowed_zone.is_empty:
        return []

    points = create_hex_grid(
        allowed_zone,
        grid_spacing
    )

    points = filter_by_spacing(
        points,
        min_spacing
    )

    placements = []

    for point in points:
        rule_checks = [
            check_rule(
                point,
                features,
                rule
            )
            for rule in rules
        ]

        placements.append(
            Placement(
                point=point,
                species_type=species_type,
                species=species,
                rationale=build_rationale(rules),
                rule_checks=rule_checks
            )
        )

    return placements


def create_plan(
    allowed_zone,
    species_type: str,
    rules: list[Rule],
    grid_spacing: float,
    min_spacing: float,
    features,
    species: str | None = None
) -> list[Placement]:
    return create_placements(
        allowed_zone=allowed_zone,
        species_type=species_type,
        rules=rules,
        grid_spacing=grid_spacing,
        min_spacing=min_spacing,
        features=features,
        species=species
    )

def build_rationale(rules: list[Rule]) -> list[Rule]:
    return [
        rule
        for rule in rules
        if rule.verified
    ]


def create_plan_with_rejections(
    area,
    species_type: str,
    rules: list[Rule],
    features,
    grid_spacing: float,
    min_spacing: float,
    species: str | None = None
):
    candidates = create_hex_grid(
        area,
        grid_spacing
    )

    placements = []
    rejections = []

    for point in candidates:
        violated_rule = find_violation(
            point,
            features,
            rules
        )

        if violated_rule is not None:
            rejections.append(
                Rejection(
                    point=point,
                    species_type=species_type,
                    violated=violated_rule
                )
            )
            continue

        placements.append(point)

    placements = filter_by_spacing(
        placements,
        min_spacing
    )

    result = []

    for point in placements:
        rule_checks = [
            check_rule(
                point,
                features,
                rule
            )
            for rule in rules
        ]

        result.append(
            Placement(
                point=point,
                species_type=species_type,
                species=species,
                rationale=build_rationale(rules),
                rule_checks=rule_checks
            )
        )

    return result, rejections