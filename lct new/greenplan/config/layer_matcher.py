#!/usr/bin/env python3
"""
Распознавание типа объекта по имени слоя DXF.

Четыре уровня, от надёжного к рискованному. Решение принимается на первом же
уровне, который сработал, и в ответе всегда указано, КАК оно принято, —
чтобы это можно было показать пользователю и записать в отчёт.

  0. override   — пользователь явно указал тип этого слоя (из конфига или UI)
  1. dictionary — токен имени найден в словаре аббревиатур проектировщиков
  2. fuzzy      — нечёткое сходство по символьным 3-граммам выше порога
  3. unknown    — не угадываем, а спрашиваем

Ключевая идея нормализации: имя слоя в проектном чертеже — это не слово,
а код. `$130$ДВ_ГП_П_БР_1000_300_150` = служебный префикс вставки + префикс
комплекта чертежа + аббревиатура объекта + габариты по ГОСТ. Информацию несёт
только аббревиатура. Поэтому:

  * срезаются префиксы вида `$130$` и ведущие подчёркивания;
  * имя бьётся на токены по _ - . пробелу и границе цифра/буква;
  * выбрасываются чисто числовые токены (габариты, диаметры, номера);
  * выбрасываются токены, встречающиеся больше чем в 60% слоёв ЭТОГО файла,
    — они относятся к комплекту чертежа, а не к объекту, и информации не несут.

Последний пункт делает систему переносимой между чертежами без ручной
настройки: в одном файле служебным окажется `ДВ_ГП_П`, в другом `ЭН`, и
определится это само.

Запуск как скрипта — отчёт по файлу:
    python layer_matcher.py чертёж.dxf
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field

# ──────────────────────────────────────────────────────────────────────────
# Словарь аббревиатур. Это рабочая заготовка — её расширяют аналитики,
# разбирая реальные имена слоёв датасета. Один токен может вести к типу
# напрямую; для спорных случаев есть приоритет: ANNOTATION проверяется первым,
# иначе выноски и размеры попадут в объекты.
# ──────────────────────────────────────────────────────────────────────────

DICTIONARY: dict[str, tuple[str, ...]] = {
    # аннотации и служебное — проверяется раньше всего
    "ANNOTATION": (
        "ВЫНОСК", "НОМЕР", "ТЕКСТ", "РАЗМЕР", "ПОДПИС", "ШТАМП", "РАМКА",
        "ЭКСПЛИК", "ВЕДОМОСТ", "ЛЕГЕНД", "ОСЬ", "ОСИ", "DEFPOINTS",
        "ВСПОМОГАТ", "НАДПИС",
    ),
    "PIPE_WATER": ("ВОДОПР", "ВОДОПРОВОД", "ХВС", "ГВС", "ВОДОСНАБ"),
    "PIPE_SEWER": ("КАНАЛИЗ", "КАН", "ФЕКАЛ", "К1", "К-1"),
    "PIPE_DRAINAGE": ("ВОДОСТОК", "ЛИВН", "ДРЕНАЖ", "ДРЕН", "К2", "К-2"),
    "PIPE_GAS": ("ГАЗОПР", "ГАЗ"),
    "PIPE_HEAT": ("ТЕПЛОС", "ТЕПЛОТР", "ТЕПЛОПР", "ТЕПЛО", "ТС", "Т1", "Т2"),
    "CABLE": (
        "КАБЕЛ", "КЛ", "СВЯЗ", "ВОЛС", "ТЕЛЕФ", "СКС", "СЛАБОТ", "ПНД",
    ),
    "POWERLINE": ("ЛЭП", "ВЛ", "ВОЗДУШ", "ОПОРА", "ОПОРЫ", "СИП"),
    "LIGHTING": ("СВЕТИЛЬНИК", "ОСВЕЩ", "ТОРШЕР", "НО", "ФОНАР"),
    "BUILDING": ("ЗДАН", "СТРОЕН", "КОРПУС", "ФАСАД", "ДОМ", "ПАВИЛЬОН"),
    "ROAD": (
        "ПРОЕЗД", "ДОРОГ", "ПЧ", "АБ", "АСФАЛЬТ", "РАЗМЕТКА", "ПАРКОВК",
        "БР", "БОРТ", "БОРДЮР", "ПОКРЫТ", "ТР-АБ", "ЩМА",
    ),
    "PAVEMENT": ("ТРОТУАР", "ПЕШЕХ", "ПЛИТК", "ДОРОЖК"),
    "SITE_BOUNDARY": ("ГРАНИЦ", "ЗАКАЗ", "УЧАСТОК", "БЛАГОУСТР", "ОТВОД"),
    "EXISTING_GREEN": ("ГАЗОН", "ОЗЕЛЕН", "ДЕРЕВ", "КУСТ", "ЦВЕТНИК", "ГЗН"),
    "MAF": ("МАФ", "СКАМ", "ОГРАЖД", "НАВЕС", "БЕСЕДК", "СТЕЛА"),
    "BIN": ("УРНА", "МУСОР", "КОНТЕЙНЕР"),
}

# Порядок проверки: аннотации первыми, дальше по убыванию специфичности.
# Короткие двухбуквенные токены (БР, ПЧ, НО, ВЛ) проверяются последними,
# чтобы не перехватывать более длинные совпадения.
PRIORITY = (
    "ANNOTATION", "SITE_BOUNDARY", "BUILDING", "PIPE_WATER", "PIPE_SEWER",
    "PIPE_DRAINAGE", "PIPE_GAS", "PIPE_HEAT", "CABLE", "POWERLINE",
    "LIGHTING", "ROAD", "PAVEMENT", "EXISTING_GREEN", "MAF", "BIN",
)

XREF_PREFIX = re.compile(r"^\$[^$]*\$")
SPLIT = re.compile(r"[_\-.\s|/\\]+")
DIGIT_BOUNDARY = re.compile(r"(?<=[А-ЯA-Z])(?=\d)|(?<=\d)(?=[А-ЯA-Z])")
NUMERIC = re.compile(r"^\d+[А-ЯA-Zх×x]*\d*$")

# Токены короче этого и не из словаря отбрасываются как шум
MIN_TOKEN = 2


@dataclass
class Match:
    """Результат распознавания одного слоя."""

    layer: str
    kind: str
    confidence: float
    method: str                      # override | dictionary | fuzzy | unknown
    evidence: str = ""               # что именно сработало — для отчёта и UI
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
    """Имя слоя → значимые токены в верхнем регистре."""
    name = XREF_PREFIX.sub("", layer).strip("_ -")
    name = DIGIT_BOUNDARY.sub("_", name.upper())
    parts = [p for p in SPLIT.split(name) if p]
    return tuple(
        p for p in parts
        if not NUMERIC.match(p) and len(p) >= MIN_TOKEN
    )


def service_tokens(layers: list[str], share: float = 0.6) -> set[str]:
    """
    Токены, встречающиеся больше чем в `share` слоёв файла.

    Это префиксы комплекта чертежа (ДВ, ГП, П, ЭН). Они одинаковы почти
    у всех слоёв, значит про объект ничего не говорят — как стоп-слова,
    только вычисленные по самому файлу, а не заданные заранее.
    """
    if not layers:
        return set()
    seen: Counter[str] = Counter()
    for layer in layers:
        seen.update(set(tokenize(layer)))
    threshold = max(2, int(len(layers) * share))
    return {t for t, n in seen.items() if n >= threshold}


def trigrams(text: str) -> set[str]:
    padded = f"  {text} "
    return {padded[i:i + 3] for i in range(len(padded) - 2)}


def similarity(a: str, b: str) -> float:
    """Коэффициент Дайса по символьным 3-граммам: 0..1."""
    ta, tb = trigrams(a), trigrams(b)
    if not ta or not tb:
        return 0.0
    return 2 * len(ta & tb) / (len(ta) + len(tb))


class LayerMatcher:
    def __init__(
        self,
        overrides: dict[str, str] | None = None,
        dictionary: dict[str, tuple[str, ...]] | None = None,
        fuzzy_threshold: float = 0.62,
    ) -> None:
        self.overrides = {k.upper(): v for k, v in (overrides or {}).items()}
        self.dictionary = dictionary or DICTIONARY
        self.fuzzy_threshold = fuzzy_threshold
        self._service: set[str] = set()

    def fit(self, layers: list[str]) -> "LayerMatcher":
        """Запомнить служебные токены этого чертежа."""
        self._service = service_tokens(layers)
        return self

    def match(self, layer: str) -> Match:
        raw = tokenize(layer)
        tokens = tuple(t for t in raw if t not in self._service) or raw

        # 0. явное указание пользователя
        if layer.upper() in self.overrides:
            return Match(
                layer, self.overrides[layer.upper()], 1.0, "override",
                "тип задан пользователем", tokens,
            )

        # 1. словарь: точное вхождение аббревиатуры
        for kind in PRIORITY:
            for abbr in self.dictionary.get(kind, ()):
                for token in tokens:
                    if token == abbr or (len(abbr) > 3 and token.startswith(abbr)):
                        return Match(
                            layer, kind, 1.0, "dictionary",
                            f"токен «{token}» → {abbr}", tokens,
                        )

        # 2. нечёткое сходство
        best = (0.0, "", "")
        for kind in PRIORITY:
            for abbr in self.dictionary.get(kind, ()):
                if len(abbr) < 4:
                    continue          # короткие сравнивать нечётко бессмысленно
                for token in tokens:
                    score = similarity(token, abbr)
                    if score > best[0]:
                        best = (score, kind, f"«{token}» ≈ «{abbr}»")
        if best[0] >= self.fuzzy_threshold:
            return Match(layer, best[1], best[0], "fuzzy", best[2], tokens)

        # 3. не угадываем
        return Match(
            layer, "UNKNOWN", 0.0, "unknown",
            f"значимые токены: {', '.join(tokens) or '—'}", tokens,
        )

    def match_all(self, layers: list[str]) -> list[Match]:
        self.fit(layers)
        return [self.match(layer) for layer in layers]


def report(path: str) -> None:
    import ezdxf

    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    counts = Counter(e.dxf.layer for e in msp)
    layers = list(counts)

    matcher = LayerMatcher()
    results = matcher.match_all(layers)

    print(f"файл: {path}")
    print(f"слоёв в modelspace: {len(layers)}, сущностей: {sum(counts.values())}")
    print(f"служебные токены чертежа: {', '.join(sorted(matcher._service)) or '—'}\n")

    by_method = Counter(m.method for m in results)
    known = sum(counts[m.layer] for m in results if m.kind not in ("UNKNOWN", "ANNOTATION"))
    print(f"{'слой':<42}{'тип':<16}{'как':<12}{'шт':>5}  обоснование")
    for m in sorted(results, key=lambda m: -counts[m.layer]):
        print(f"{m.layer[:41]:<42}{m.kind:<16}{m.method:<12}{counts[m.layer]:>5}  {m.evidence}")

    print(f"\nпо способам: {dict(by_method)}")
    print(f"сущностей с определённым типом: {known} из {sum(counts.values())}")
    unknown = [m.layer for m in results if m.method == "unknown"]
    if unknown:
        print(f"\nнужно уточнить у пользователя ({len(unknown)}): {', '.join(unknown[:10])}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("укажите путь к DXF")
    report(sys.argv[1])

