import argparse
from pathlib import Path

import ezdxf
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend


def render_dxf(input_path, output_path, dpi=220, layout_name="Model"):
    doc = ezdxf.readfile(input_path)

    if layout_name.lower() == "model":
        layout = doc.modelspace()
        layout_title = "Model"
    else:
        if layout_name not in doc.layouts:
            available = ", ".join(layout.name for layout in doc.layouts)
            raise ValueError(
                f"Layout '{layout_name}' not found. Available layouts: {available}"
            )
        layout = doc.layouts.get(layout_name)
        layout_title = layout_name

    fig = plt.figure(figsize=(16, 11), facecolor="white")
    ax = fig.add_axes([0.015, 0.015, 0.97, 0.97])
    ax.set_facecolor("white")
    ax.set_aspect("equal", adjustable="datalim")
    ax.axis("off")

    context = RenderContext(doc)
    backend = MatplotlibBackend(ax)
    frontend = Frontend(context, backend)
    frontend.draw_layout(layout, finalize=True)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        output_path,
        dpi=dpi,
        facecolor="white",
        bbox_inches="tight",
        pad_inches=0.1,
    )
    plt.close(fig)
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Рендерит DXF целиком в PNG, не изменяя исходный файл."
    )
    parser.add_argument("dxf", help="Путь к исходному DXF")
    parser.add_argument(
        "--output",
        default="data/debug_visualization_v3/full_drawing.png",
        help="Путь к итоговому PNG",
    )
    parser.add_argument("--dpi", type=int, default=220, help="Разрешение PNG")
    parser.add_argument(
        "--layout",
        default="Model",
        help="Имя листа/layout; по умолчанию Model (modelspace)",
    )
    args = parser.parse_args()

    try:
        output = render_dxf(args.dxf, args.output, args.dpi, args.layout)
    except Exception as exc:
        raise SystemExit(
            f"Не удалось отрисовать DXF: {exc}\n"
            "Если ошибка связана с ezdxf drawing backend, обнови ezdxf в активном venv."
        )

    print(f"Изображение сохранено: {output.resolve()}")
    print("Исходный DXF не изменён.")


if __name__ == "__main__":
    main()
