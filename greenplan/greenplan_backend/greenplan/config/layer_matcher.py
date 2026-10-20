from __future__ import annotations

import re
import sys
from collections import Counter
from dataclasses import dataclass, field

DICTIONARY: dict[str, tuple[str, ...]] = {
    "ANNOTATION": (
        "ВЫНОСК", "ССЫЛК", "НОМЕР", "ТЕКСТ", "РАЗМЕР", "ПОДПИС", "НАДПИС", "ШТАМП",
        "РАМКА", "ЭКСПЛИК", "ВЕДОМОСТ", "ЛЕГЕНД", "УСЛОВН", "ОБОЗНАЧ", "ОФР",
        "ОСЬ", "ОСИ", "ВСПОМОГАТ", "КАРТИНК", "DEFPOINTS", "ДЕМОНТАЖ", "РАЗБОРК", "СНОС",
        "ВЕРТИКАЛ", "ВОПРОС", "ЗАМЕЧАН",
    ),
    "SITE_BOUNDARY": ("ГРАНИЦ", "ЗАКАЗ", "УЧАСТОК", "БЛАГОУСТР", "ОТВОД"),
    "BUILDING": ("ЗДАН", "СТРОЕН", "КОРПУС", "ФАСАД", "ДОМ", "ПАВИЛЬОН"),
    "PIPE_WATER": ("ВОДОПР", "ВОДОПРОВОД", "ХВС", "ГВС", "ВОДОСНАБ"),
    "PIPE_SEWER": ("КАНАЛИЗ", "КАН", "ФЕКАЛ"),
    "PIPE_DRAINAGE": ("ВОДОСТОК", "ЛИВН", "ДРЕНАЖ", "ДРЕН"),
    "PIPE_GAS": ("ГАЗОПР", "ГАЗ"),
    "PIPE_HEAT": ("ТЕПЛОС", "ТЕПЛОТР", "ТЕПЛОПР", "ТЕПЛО", "ТС"),
    "CABLE": ("КАБЕЛ", "КЛ", "СВЯЗ", "ВОЛС", "ТЕЛЕФ", "СКС", "СЛАБОТ", "ПНД"),
    "POWERLINE": ("ЛЭП", "ВЛ", "ВОЗДУШ", "СИП"),
    "LIGHTING": (
        "СВЕТИЛЬНИК", "ОСВЕЩ", "ТОРШЕР", "ФОНАР", "СВЕТ", "LED", "ОПОРА", "ОПОРЫ", "МАЧТ", "НО",
    ),
    "TRAM_TRACK": ("ТРАМВ",),
    "RETAINING_WALL": ("ПОДПОРН",),
    "SLOPE": ("ОТКОС", "ТЕРРАС"),
    "ROAD": (
        "ПРОЕЗД", "ДОРОГ", "ПЧ", "АБ", "АСФАЛЬТ", "РАЗМЕТКА", "ПАРКОВК", "БР", "БОРТ",
        "БОРДЮР", "ПОКРЫТ", "ЩМА",
    ),
    "PAVEMENT": ("ТРОТУАР", "ПЕШЕХ", "ПЛИТК", "ДОРОЖК"),
    "EXISTING_GREEN": ("ГАЗОН", "ОЗЕЛЕН", "ДЕРЕВ", "КУСТ", "ЦВЕТНИК", "ГЗН"),
    "MAF": ("МАФ", "СКАМ", "ОГРАЖД", "НАВЕС", "БЕСЕДК", "СТЕЛА", "ЛЕСТНИЦ", "ПАНДУС", "КОНТЕЙНЕРН"),
    "BIN": ("УРНА", "МУСОР", "КОНТЕЙНЕР"),
}

PRIORITY = (
    "ANNOTATION", "SITE_BOUNDARY", "BUILDING", "PIPE_WATER", "PIPE_SEWER", "PIPE_DRAINAGE",
    "PIPE_GAS", "PIPE_HEAT", "CABLE", "POWERLINE", "LIGHTING", "TRAM_TRACK", "RETAINING_WALL", "SLOPE",
    "ROAD", "PAVEMENT", "EXISTING_GREEN", "MAF", "BIN",
)

XREF_PREFIX = re.compile(r"^\$[^$]*\$+")
SPLIT = re.compile(r"[_\-.\s|/\\$!#@*()\[\]{}+,;:=~^&%']+")
DIGIT_BOUNDARY = re.compile(r"(?<=[А-ЯЁA-Z])(?=\d)|(?<=\d)(?=[А-ЯЁA-Z])")
NUMERIC = re.compile(r"^\d+[А-ЯЁA-ZХ×X]*\d*$")
MIN_TOKEN = 2


@dataclass
class Match:
    layer: str
    kind: str
    confidence: float
    method: str
    evidence: str = ""
    tokens: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict:
        return {
            "layer": self.layer,
            "kind": self.kind,
            "confidence": round(self.confidence, 3),
            "method": self.method,
            "evidence": self.evidence,
        }


def tokenize(layer: str) -> tuple[str, ...]:
    name = XREF_PREFIX.sub("", layer).strip("_ -")
    name = DIGIT_BOUNDARY.sub("_", name.upper())
    parts = [part for part in SPLIT.split(name) if part]
    return tuple(part for part in parts if not NUMERIC.match(part) and len(part) >= MIN_TOKEN)


def service_tokens(layers: list[str], share: float = 0.6) -> set[str]:
    if not layers:
        return set()
    seen: Counter[str] = Counter()
    for layer in layers:
        seen.update(set(tokenize(layer)))
    threshold = max(2, int(len(layers) * share))
    return {token for token, count in seen.items() if count >= threshold}


def trigrams(text: str) -> set[str]:
    padded = f"  {text} "
    return {padded[i:i + 3] for i in range(len(padded) - 2)}


def similarity(a: str, b: str) -> float:
    left, right = trigrams(a), trigrams(b)
    if not left or not right:
        return 0.0
    return 2 * len(left & right) / (len(left) + len(right))


class LayerMatcher:
    def __init__(
        self,
        overrides: dict[str, str] | None = None,
        dictionary: dict[str, tuple[str, ...]] | None = None,
        fuzzy_threshold: float = 0.62,
    ) -> None:
        self.overrides = {key.upper(): value for key, value in (overrides or {}).items()}
        self.dictionary = dictionary or DICTIONARY
        self.fuzzy_threshold = fuzzy_threshold
        self._service: set[str] = set()

    @property
    def service(self) -> set[str]:
        return set(self._service)

    def fit(self, layers: list[str]) -> "LayerMatcher":
        self._service = service_tokens(layers)
        return self

    def match(self, layer: str) -> Match:
        raw = tokenize(layer)
        tokens = tuple(token for token in raw if token not in self._service) or raw

        if layer.upper() in self.overrides:
            return Match(layer, self.overrides[layer.upper()], 1.0, "override",
                         "тип задан пользователем", tokens)

        for kind in PRIORITY:
            for abbr in self.dictionary.get(kind, ()):
                for token in tokens:
                    if token == abbr or (len(abbr) > 3 and token.startswith(abbr)):
                        return Match(layer, kind, 1.0, "dictionary", f"«{token}» → {abbr}", tokens)

        best = (0.0, "", "")
        for kind in PRIORITY:
            for abbr in self.dictionary.get(kind, ()):
                if len(abbr) < 4:
                    continue
                for token in tokens:
                    score = similarity(token, abbr)
                    if score > best[0]:
                        best = (score, kind, f"«{token}» ≈ «{abbr}»")
        if best[0] >= self.fuzzy_threshold:
            return Match(layer, best[1], best[0], "fuzzy", best[2], tokens)

        return Match(layer, "UNKNOWN", 0.0, "unknown", ", ".join(tokens), tokens)

    def match_all(self, layers: list[str]) -> list[Match]:
        self.fit(layers)
        return [self.match(layer) for layer in layers]


def report(path: str) -> None:
    import ezdxf

    counts = Counter(entity.dxf.layer for entity in ezdxf.readfile(path).modelspace())
    matcher = LayerMatcher()
    results = matcher.match_all(list(counts))
    total = sum(counts.values())
    typed = sum(counts[m.layer] for m in results if m.kind not in ("UNKNOWN", "ANNOTATION"))

    print(f"{path}: {len(counts)} слоёв, {total} объектов")
    print(f"служебные токены: {', '.join(sorted(matcher.service)) or '—'}")
    for m in sorted(results, key=lambda m: -counts[m.layer]):
        print(f"{counts[m.layer]:>6}  {m.layer[:44]:<45}{m.kind:<16}{m.method:<11}{m.evidence}")
    print(f"с типом: {typed} из {total} ({typed / max(total, 1):.0%})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("python -m greenplan.config.layer_matcher чертёж.dxf")
    report(sys.argv[1])
