from shapely.geometry import Point

from greenplan.writer.dxf_writer import write_placements


write_placements(
    "test.dxf",
    "out.dxf",
    [Point(50, 20)]
)