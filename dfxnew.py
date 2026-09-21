import os
os.makedirs("data", exist_ok=True)
import ezdxf

doc = ezdxf.new("R2010", setup=True)
msp = doc.modelspace()

# Слои подосновы
for name, color in [
    ("SITE_BOUNDARY", 7),
    ("BUILDING", 8),
    ("ROAD", 9),
    ("UTIL_WATER", 5),
    ("UTIL_SEWER", 6),
    ("UTIL_CABLE", 4),
]:
    doc.layers.add(name, color=color)

# Границы участка (замкнутая полилиния, м)
msp.add_lwpolyline(
    [(0, 0), (80, 0), (80, 50), (0, 50)],
    close=True, dxfattribs={"layer": "SITE_BOUNDARY"},
)

# Здание
msp.add_lwpolyline(
    [(10, 25), (35, 25), (35, 45), (10, 45)],
    close=True, dxfattribs={"layer": "BUILDING"},
)

# Дорога (полоса)
msp.add_lwpolyline(
    [(0, 5), (80, 5), (80, 15), (0, 15)],
    close=True, dxfattribs={"layer": "ROAD"},
)

# Коммуникации (линии)
msp.add_lwpolyline([(0, 20), (80, 20)], dxfattribs={"layer": "UTIL_WATER"})
msp.add_lwpolyline([(40, 0), (40, 50)], dxfattribs={"layer": "UTIL_SEWER"})
msp.add_lwpolyline([(60, 0), (60, 50)], dxfattribs={"layer": "UTIL_CABLE"})

doc.saveas("data/test.dxf")
print("data/test.dxf создан")