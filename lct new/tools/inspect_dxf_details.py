
import argparse
import json
from collections import Counter
from pathlib import Path

import ezdxf


def inspect_virtual_entity(entity):
    kind = entity.dxftype()
    result = {"type": kind}

    if kind == "LINE":
        start = entity.dxf.start
        end = entity.dxf.end

        result["start"] = [
            round(start.x, 3),
            round(start.y, 3),
        ]
        result["end"] = [
            round(end.x, 3),
            round(end.y, 3),
        ]

        result["length"] = round(
            ((end.x - start.x) ** 2 + (end.y - start.y) ** 2) ** 0.5,
            3,
        )

    elif kind == "LWPOLYLINE":
        points = list(entity.get_points("xy"))
        result["closed"] = entity.closed
        result["vertices"] = len(points)
        result["points"] = [
            [round(x, 3), round(y, 3)]
            for x, y in points
        ]

        length = 0.0

        for i in range(1, len(points)):
            x1, y1 = points[i - 1]
            x2, y2 = points[i]
            length += ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5

        if entity.closed and len(points) > 1:
            x1, y1 = points[-1]
            x2, y2 = points[0]
            length += ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5

        result["length"] = round(length, 3)

    elif kind == "POLYLINE":
        vertices = list(entity.vertices)
        result["closed"] = entity.is_closed
        result["vertices"] = len(vertices)
        result["points"] = [
            [
                round(vertex.dxf.location.x, 3),
                round(vertex.dxf.location.y, 3),
            ]
            for vertex in vertices
        ]

    elif kind == "CIRCLE":
        center = entity.dxf.center
        result["center"] = [
            round(center.x, 3),
            round(center.y, 3),
        ]
        result["radius"] = round(entity.dxf.radius, 3)

    elif kind == "ARC":
        center = entity.dxf.center
        result["center"] = [
            round(center.x, 3),
            round(center.y, 3),
        ]
        result["radius"] = round(entity.dxf.radius, 3)
        result["start_angle"] = round(entity.dxf.start_angle, 3)
        result["end_angle"] = round(entity.dxf.end_angle, 3)

    elif kind == "TEXT":
        result["text"] = entity.dxf.text

    elif kind == "MTEXT":
        result["text"] = entity.text[:200]

    elif kind == "POINT":
        point = entity.dxf.location
        result["point"] = [
            round(point.x, 3),
            round(point.y, 3),
        ]

    return result


def get_insert_details(entity):
    block_name = entity.dxf.name

    insert_point = entity.dxf.insert

    result = {
        "block_name": block_name,
        "insert": [
            round(insert_point.x, 3),
            round(insert_point.y, 3),
            round(insert_point.z, 3),
        ],
        "scale": [
            round(entity.dxf.get("xscale", 1.0), 3),
            round(entity.dxf.get("yscale", 1.0), 3),
            round(entity.dxf.get("zscale", 1.0), 3),
        ],
        "rotation": round(entity.dxf.get("rotation", 0.0), 3),
        "attributes": {},
        "block_entities": [],
        "block_entity_count": 0,
        "virtual_entities": [],
        "virtual_entity_count": 0,
        "virtual_entity_errors": [],
    }

    for attribute in entity.attribs:
        result["attributes"][attribute.dxf.tag] = attribute.dxf.text

    document = entity.doc

    if document is not None and block_name in document.blocks:
        block = document.blocks[block_name]

        block_entities = [
            item for item in block
            if item.dxftype() not in ("ATTDEF", "ENDBLK")
        ]

        result["block_entities"] = [
            item.dxftype() for item in block_entities
        ]
        result["block_entity_count"] = len(block_entities)

    try:
        for virtual_entity in entity.virtual_entities():
            try:
                result["virtual_entities"].append(
                    inspect_virtual_entity(virtual_entity)
                )
            except Exception as error:
                result["virtual_entity_errors"].append(
                    f"{virtual_entity.dxftype()}: {error}"
                )

    except Exception as error:
        result["virtual_entity_errors"].append(str(error))

    result["virtual_entity_count"] = len(result["virtual_entities"])

    return result


def inspect_entity(entity):
    kind = entity.dxftype()
    result = {"type": kind}

    if kind == "INSERT":
        result.update(get_insert_details(entity))


    elif kind == "LWPOLYLINE":

        result["closed"] = entity.closed

        points = list(entity.get_points("xy"))

        result["vertices"] = len(points)

        length = 0.0

        for i in range(1, len(points)):
            x1, y1 = points[i - 1]

            x2, y2 = points[i]

            length += ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5

        if entity.closed and len(points) > 1:
            x1, y1 = points[-1]

            x2, y2 = points[0]

            length += ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5

        result["length"] = round(length, 3)


    elif kind == "POLYLINE":
        result["closed"] = entity.is_closed
        result["vertices"] = len(entity.vertices)

    elif kind == "LINE":
        start = entity.dxf.start
        end = entity.dxf.end
        result["start"] = [round(start.x, 3), round(start.y, 3)]
        result["end"] = [round(end.x, 3), round(end.y, 3)]

    elif kind == "TEXT":
        result["text"] = entity.dxf.text

    elif kind == "MTEXT":
        result["text"] = entity.text[:300]

    elif kind == "POINT":
        point = entity.dxf.location
        result["point"] = [round(point.x, 3), round(point.y, 3)]

    return result


def inspect_file(path):
    document = ezdxf.readfile(path)
    modelspace = document.modelspace()

    layers = {}

    for entity in modelspace:
        layer_name = entity.dxf.layer

        if layer_name not in layers:
            layers[layer_name] = {
                "entity_count": 0,
                "types": Counter(),
                "examples": [],
            }

        info = layers[layer_name]
        info["entity_count"] += 1
        info["types"][entity.dxftype()] += 1

        if len(info["examples"]) < 12:
            info["examples"].append(inspect_entity(entity))

    return {
        "file": path.name,
        "layers": {
            name: {
                "entity_count": info["entity_count"],
                "entity_types": dict(info["types"]),
                "examples": info["examples"],
            }
            for name, info in sorted(layers.items())
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="DXF-файл или папка с DXF")
    parser.add_argument(
        "--output",
        default="data/dxf_details.json",
        help="Путь для JSON-отчёта",
    )
    parser.add_argument(
        "--layers",
        nargs="*",
        help="Проверить только указанные слои",
    )
    args = parser.parse_args()

    source = Path(args.input)

    if source.is_file():
        files = [source]
    elif source.is_dir():
        files = sorted(source.glob("*.dxf"))
    else:
        raise FileNotFoundError(f"Не найден путь: {source}")

    report = []

    for file_path in files:
        try:
            details = inspect_file(file_path)

            if args.layers:
                details["layers"] = {
                    name: info
                    for name, info in details["layers"].items()
                    if any(
                        pattern.casefold() in name.casefold()
                        for pattern in args.layers
                    )
                }

            report.append(details)
            print(
                f"OK: {file_path.name}; "
                f"слоёв в отчёте: {len(details['layers'])}"
            )

        except Exception as error:
            print(f"ОШИБКА: {file_path.name}: {error}")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\nОтчёт сохранён: {output.resolve()}")


if __name__ == "__main__":
    main()
