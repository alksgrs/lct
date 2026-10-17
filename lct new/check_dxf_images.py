from pathlib import Path
import ezdxf

folder = Path(__file__).resolve().parent

for path in folder.glob("*.dxf"):
    print(f"\n{'=' * 60}")
    print(f"Файл: {path.name}")

    try:
        doc = ezdxf.readfile(path)
        images = list(doc.modelspace().query("IMAGE"))
        definitions = list(doc.objects.query("IMAGEDEF"))

        print("Объектов в модели:", len(doc.modelspace()))
        print("Растровых изображений:", len(images))
        print("Определений изображений:", len(definitions))

        for definition in definitions:
            print(
                "IMAGEDEF:",
                "имя =", repr(definition.dxf.filename),
                "загружено =", definition.dxf.loaded,
            )

        for image in images:
            print(
                "IMAGE:",
                "слой =", image.dxf.layer,
                "вставка =", tuple(image.dxf.insert),
                "размер =", tuple(image.dxf.image_size),
            )

    except Exception as error:
        print("Ошибка чтения:", error)
