import ezdxf


doc = ezdxf.new("R2010")
modelspace = doc.modelspace()

doc.layers.add("SITE_BOUNDARY")
doc.layers.add("PIPE_WATER")
doc.layers.add("BUILDING")

modelspace.add_lwpolyline(
    [
        (0, 0),
        (100, 0),
        (100, 60),
        (0, 60)
    ],
    close=True,
    dxfattribs={"layer": "SITE_BOUNDARY"}
)

modelspace.add_line(
    (0, 25),
    (100, 25),
    dxfattribs={"layer": "PIPE_WATER"}
)

modelspace.add_lwpolyline(
    [
        (35, 35),
        (65, 35),
        (65, 50),
        (35, 50)
    ],
    close=True,
    dxfattribs={"layer": "BUILDING"}
)

doc.saveas("test.dxf")