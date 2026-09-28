import ezdxf


path = r"C:\Users\Aleksandra\PycharmProjects\LCT\lct\_06_10000176_Генплан_Олимп.dxf"

doc = ezdxf.readfile(path)
modelspace = doc.modelspace()

for entity in modelspace:
    layer = entity.dxf.layer

    if layer not in [
        "ГРАНИЦА_ЗАКАЗА",
        "ДВ_ГП_П_ГРАНИЦА_РАБОТ"
    ]:
        continue

    print()
    print("Слой:", layer)
    print("Тип:", entity.dxftype())

    if entity.dxftype() == "LWPOLYLINE":
        points = [
            (point[0], point[1])
            for point in entity.get_points()
        ]

        print("Точек:", len(points))
        print("Замкнута:", entity.closed)
        print("Первые точки:")

        for point in points[:10]:
            print(" ", point)