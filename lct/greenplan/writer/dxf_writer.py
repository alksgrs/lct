import ezdxf

from shapely.geometry import Point


def write_placements(
    input_path: str,
    output_path: str,
    points: list[Point],
    layer_name: str = "PLANTING_TREES"
) -> None:
    doc = ezdxf.readfile(input_path)

    if layer_name not in doc.layers:
        doc.layers.add(layer_name)

    modelspace = doc.modelspace()

    for point in points:
        modelspace.add_point(
            (point.x, point.y),
            dxfattribs={"layer": layer_name}
        )

    doc.saveas(output_path)