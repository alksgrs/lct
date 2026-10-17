from greenplan.models import FeatureKind

# Типы, которые можно назначить слою вручную. ANNOTATION — «служебный слой,
# в фичи не попадает». UNKNOWN назначать нельзя: это отсутствие типа.
ALLOWED_KINDS = (
    {kind.value for kind in FeatureKind if kind != FeatureKind.UNKNOWN}
    | {"ANNOTATION"}
)


def parse_override(text: str) -> tuple[str, str]:
    """'ГП_300_300=ROAD' -> ('ГП_300_300', 'ROAD')."""
    layer, separator, kind = text.rpartition("=")
    layer = layer.strip()
    kind = kind.strip().upper()

    if not separator or not layer:
        raise ValueError(
            f"ожидается формат СЛОЙ=ТИП, получено: {text!r}"
        )

    if kind not in ALLOWED_KINDS:
        raise ValueError(
            f"неизвестный тип {kind!r}; допустимо: "
            + ", ".join(sorted(ALLOWED_KINDS))
        )

    return layer, kind

