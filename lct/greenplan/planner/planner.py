from shapely.geometry import Point

from greenplan.models import Placement, Rule


def create_placement(
    allowed_zone,
    species_type: str,
    rule: Rule,
    species: str | None = None
) -> Placement:
    if allowed_zone.is_empty:
        raise ValueError("Allowed zone is empty")

    point = allowed_zone.representative_point()

    return Placement(
        point=point,
        species_type=species_type,
        species=species,
        rationale=[rule]
    )

