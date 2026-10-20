from greenplan.models import FeatureKind

ALLOWED_KINDS = {kind.value for kind in FeatureKind if kind != FeatureKind.UNKNOWN} | {"ANNOTATION"}


def parse_override(text: str) -> tuple[str, str]:
    layer, separator, kind = text.rpartition("=")
    layer, kind = layer.strip(), kind.strip().upper()
    if not separator or not layer:
        raise ValueError(f"ожидается формат СЛОЙ=ТИП, получено: {text!r}")
    if kind not in ALLOWED_KINDS:
        raise ValueError(f"неизвестный тип {kind!r}; допустимо: " + ", ".join(sorted(ALLOWED_KINDS)))
    return layer, kind


def validate_overrides(overrides: dict[str, str]) -> dict[str, str]:
    clean = {}
    for layer, kind in overrides.items():
        kind = str(kind).strip().upper()
        if kind not in ALLOWED_KINDS:
            raise ValueError(f"неизвестный тип {kind!r} для слоя «{layer}»")
        clean[str(layer)] = kind
    return clean
