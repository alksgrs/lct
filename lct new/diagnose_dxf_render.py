import argparse
from collections import Counter, defaultdict
from pathlib import Path

import ezdxf


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dxf", help="Путь к DXF-файлу")
    parser.add_argument(
        "--output",
        default="data/debug_visualization_v3/render_report.txt",
        help="Путь к отчёту",
    )
    args = parser.parse_args()

    doc = ezdxf.readfile(args.dxf)
    msp = doc.modelspace()

    lines = []
    lines.append("ОТЧЁТ О СТРУКТУРЕ DXF")
    lines.append(f"Файл: {args.dxf}")
    lines.append(f"Версия DXF: {doc.dxfversion}")
    lines.append("")

    entity_types = Counter()
    layer_types = defaultdict(Counter)
    inserts = Counter()
    block_types = defaultdict(Counter)
    empty_blocks = []
    total = 0

    for entity in msp:
        kind = entity.dxftype()
        layer = entity.dxf.layer if entity.dxf.hasattr("layer") else "?"
        entity_types[kind] += 1
        layer_types[layer][kind] += 1
        total += 1

        if kind == "INSERT":
            inserts[entity.dxf.name] += 1

    lines.append(f"Всего объектов в Modelspace: {total}")
    lines.append("")
    lines.append("ТИПЫ ОБЪЕКТОВ В MODESPACE")

    for kind, count in entity_types.most_common():
        lines.append(f"{kind}: {count}")

    lines.append("")
    lines.append("СЛОИ И ТИПЫ ОБЪЕКТОВ")

    for layer in sorted(layer_types):
        counts = layer_types[layer]
        summary = ", ".join(
            f"{kind}: {count}" for kind, count in counts.most_common()
        )
        try:
            layer_obj = doc.layers.get(layer)
            visible = not layer_obj.is_off() and not layer_obj.is_frozen()
            color = layer_obj.dxf.color
            linetype = layer_obj.dxf.linetype
        except Exception:
            visible = "неизвестно"
            color = "неизвестно"
            linetype = "неизвестно"

        lines.append(
            f"{layer} | видимый={visible} | цвет={color} | "
            f"тип линии={linetype} | {summary}"
        )

    lines.append("")
    lines.append("ВСТАВКИ БЛОКОВ В MODESPACE")

    if inserts:
        for name, count in inserts.most_common():
            lines.append(f"{name}: {count}")
    else:
        lines.append("INSERT не найдены")

    lines.append("")
    lines.append("СОДЕРЖИМОЕ ОПРЕДЕЛЕНИЙ БЛОКОВ")

    for block in doc.blocks:
        name = block.name

        if name.startswith("*Model_Space") or name.startswith("*Paper_Space"):
            continue

        counts = Counter(entity.dxftype() for entity in block)
        block_types[name].update(counts)

        if not counts:
            empty_blocks.append(name)

        summary = ", ".join(
            f"{kind}: {count}" for kind, count in counts.most_common()
        )
        lines.append(f"{name}: {summary if summary else 'пустой блок'}")

    lines.append("")
    lines.append(f"Пустых определений блоков: {len(empty_blocks)}")

    if empty_blocks:
        lines.append(", ".join(empty_blocks[:100]))

    lines.append("")
    lines.append("НАСТРОЙКИ ЧЕРТЕЖА")
    for variable in (
        "$INSUNITS",
        "$LUNITS",
        "$LUPREC",
        "$MEASUREMENT",
        "$LIMMIN",
        "$LIMMAX",
        "$EXTMIN",
        "$EXTMAX",
    ):
        try:
            value = doc.header.get(variable)
            lines.append(f"{variable}: {value}")
        except Exception:
            lines.append(f"{variable}: не удалось прочитать")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")

    print(f"Отчёт сохранён: {output.resolve()}")
    print(f"Объектов в Modelspace: {total}")
    print(f"Слоёв: {len(layer_types)}")
    print(f"Разных вставок блоков: {len(inserts)}")


if __name__ == "__main__":
    main()

