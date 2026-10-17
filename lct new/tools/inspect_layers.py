
import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

import ezdxf


GENERATED_PREFIXES = (
    "out",
    "tree",
    "trees",
    "shrubs",
    "groundcover",
)


def inspect_dxf(path):
    document = ezdxf.readfile(path)
    modelspace = document.modelspace()

    entity_counts = defaultdict(Counter)
    examples = defaultdict(list)
    total_counts = Counter()

    for entity in modelspace:
        layer = entity.dxf.get("layer", "0")
        entity_type = entity.dxftype()

        entity_counts[layer][entity_type] += 1
        total_counts[layer] += 1

        if len(examples[layer]) < 3:
            examples[layer].append(entity_type)

    return total_counts, entity_counts, examples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("layer_catalog.csv"),
    )
    args = parser.parse_args()

    rows = []

    for path in sorted(args.directory.glob("*.dxf")):
        if path.stem.lower().startswith(GENERATED_PREFIXES):
            continue

        try:
            totals, counts, examples = inspect_dxf(path)

            for layer, total in totals.items():
                rows.append({
                    "file": path.name,
                    "layer": layer,
                    "entity_count": total,
                    "entity_types": "; ".join(
                        f"{kind}: {count}"
                        for kind, count in sorted(counts[layer].items())
                    ),
                    "examples": "; ".join(examples[layer]),
                })

            print(f"OK: {path.name}, слоёв: {len(totals)}")

        except Exception as error:
            print(f"ОШИБКА: {path.name}: {error}")

    args.output.parent.mkdir(parents=True, exist_ok=True)

    with args.output.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "file",
                "layer",
                "entity_count",
                "entity_types",
                "examples",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Каталог сохранён: {args.output.resolve()}")
    print(f"Всего записей: {len(rows)}")


if __name__ == "__main__":
    main()
