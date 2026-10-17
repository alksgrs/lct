from pathlib import Path
import ezdxf
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

folder = Path(__file__).resolve().parent
output = folder / "data" / "extracted_images"
output.mkdir(parents=True, exist_ok=True)

files = [
    "10001759 НО 3-я Парковая ул.dxf",
    "_06_10000176_Генплан_Олимп.dxf",
    "Харьковская АПОТ_2026-01-15.dxf",
]

for filename in files:
    path = folder / filename
    if not path.exists():
        print("Файл не найден:", filename)
        continue

    doc = ezdxf.readfile(path)
    images = list(doc.modelspace().query("IMAGE"))

    print(f"\n{filename}: изображений — {len(images)}")

    for index, image in enumerate(images, start=1):
        definition = doc.entitydb.get(image.dxf.image_def_handle)
        image_path = ""

        if definition is not None:
            image_path = definition.dxf.filename or ""

        print("  Путь в DXF:", repr(image_path))

        if not image_path:
            print("  Пропуск: путь к изображению не задан.")
            continue

        from pathlib import Path

        downloads = Path.home() / "Downloads"

        # Внутри цикла, после получения image_path:
        filename = Path(image_path).name

        matches = list(downloads.rglob(filename))

        if matches:
            source = matches[0]
            print("Найдена подложка:", source)
        else:
            print("Подложка не найдена:", filename)
            continue

        try:
            import matplotlib.image as mpimg

            pixels = mpimg.imread(source)
            fig, ax = plt.subplots(figsize=(12, 8))
            ax.imshow(pixels)
            ax.axis("off")
            fig.tight_layout()

            result = output / f"{path.stem}_image_{index}.png"
            fig.savefig(result, dpi=150, bbox_inches="tight")
            plt.close(fig)

            print("  Изображение сохранено:", result)
        except Exception as error:
            print("  Не удалось прочитать изображение:", error)

print("\nГотово.")

