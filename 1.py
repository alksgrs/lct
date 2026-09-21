import ezdxf

def read_dxf(filename):
    doc = ezdxf.readfile(filename)
    modelspace = doc.modelspace()

    print("DXF успешно загружен")
    print("Слои:")

    for layer in doc.layers:
        print("-", layer.dxf.name)

    print("\nОбъекты:")

    count = 0

    for entity in modelspace:
        count += 1
        print(
            count,
            "| тип:", entity.dxftype(),
            "| слой:", entity.dxf.layer
        )

    print("\nВсего объектов:", count)

    return doc, modelspace


filename = input("Введите путь к DXF-файлу: ")

try:
    doc, modelspace = read_dxf(filename)
except Exception as e:
    print("Ошибка при чтении DXF:")
    print(e)

#деление на шестигранники

from shapely.geometry import Polygon


def create_hexagon(x, y, radius):
    points = []

    for i in range(6):
        angle = 3.141592653589793 / 3 * i
        px = x + radius * __import__("math").cos(angle)
        py = y + radius * __import__("math").sin(angle)
        points.append((px, py))

    return Polygon(points)


def create_hex_grid(min_x, min_y, max_x, max_y, radius):
    import math

    hexagons = []

    width = math.sqrt(3) * radius
    height = 1.5 * radius

    row = 0
    y = min_y

    while y <= max_y:
        offset = width / 2 if row % 2 else 0
        x = min_x + offset

        while x <= max_x:
            hexagon = create_hexagon(x, y, radius)

            if hexagon.intersects(
                Polygon([
                    (min_x, min_y),
                    (max_x, min_y),
                    (max_x, max_y),
                    (min_x, max_y)
                ])
            ):
                hexagons.append({
                    "id": len(hexagons),
                    "geometry": hexagon,
                    "center": (x, y)
                })

            x += width

        y += height
        row += 1

    return hexagons


#что у нас вообще есть и какое

from shapely.geometry import LineString


def read_dxf(filename):
    doc = ezdxf.readfile(filename)
    modelspace = doc.modelspace()

    objects = []

    for entity in modelspace:
        layer = entity.dxf.layer
        entity_type = entity.dxftype()

        if entity_type == "LINE":
            start = entity.dxf.start
            end = entity.dxf.end

            geometry = LineString([
                (start.x, start.y),
                (end.x, end.y)
            ])

            objects.append({
                "type": "LINE",
                "layer": layer,
                "geometry": geometry
            })

        elif entity_type == "LWPOLYLINE":
            points = []

            for point in entity.get_points():
                points.append((point[0], point[1]))

            if len(points) >= 3:
                geometry = Polygon(points)

                objects.append({
                    "type": "POLYGON",
                    "layer": layer,
                    "geometry": geometry
                })

    return doc, objects