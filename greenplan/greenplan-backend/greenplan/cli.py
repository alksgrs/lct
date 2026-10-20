import argparse
import sys
from pathlib import Path

from greenplan.config.overrides import parse_override
from greenplan.constraints.constraints import BOUNDARY_LABELS
from greenplan.pipeline import run_plan
from greenplan.planner.hex_grid import AreaTooLarge
from greenplan.writer.dxf_writer import write_plan
from greenplan.writer.serialize import greening_to_dict
from greenplan.writer.json_writer import write_placements_json

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_RULES = str(BASE_DIR / "data" / "rules" / "regulations.yaml")
DEFAULT_PLANTING = str(BASE_DIR / "data" / "rules" / "planting.yaml")
DEFAULT_LAYERS = str(BASE_DIR / "data" / "config" / "layers.yaml")


def run(input_path, output_path, species_type="tree", rules_path=DEFAULT_RULES,
        planting_path=DEFAULT_PLANTING, json_output_path=None, layers_path=DEFAULT_LAYERS,
        overrides=None, boundary_layer=None):
    species = ("tree", "shrub") if species_type == "all" else (species_type,)
    if json_output_path is None:
        json_output_path = str(Path(output_path).with_suffix(".json"))

    result = run_plan(input_path, rules_path, planting_path, layers_path,
                      species=species, overrides=overrides, boundary_layer=boundary_layer)
    parsed = result.site.parsed

    greening = greening_to_dict(result.greening)
    write_plan(input_path, output_path, result.placements, greening)
    write_placements_json(
        result.placements,
        json_output_path,
        input_path,
        species_type,
        result.rejections,
        [f"Неизвестный слой: {item['layer']}" for item in parsed.unresolved_layers],
        parsed.unresolved_layers,
        result.site.boundary_method,
        result.site.boundary_outliers,
        greening,
    )
    return result


def _override_arg(text):
    try:
        return parse_override(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="greenplan",
                                     description="План озеленения по DXF с проверкой нормативных отступов")
    parser.add_argument("input", help="исходный DXF")
    parser.add_argument("--output", default="out.dxf", help="выходной DXF")
    parser.add_argument("--json", default=None, help="отчёт с обоснованиями, по умолчанию рядом с DXF")
    parser.add_argument("--species", default="tree", choices=["tree", "shrub", "all"])
    parser.add_argument("--rules", default=DEFAULT_RULES, help="справочник норм")
    parser.add_argument("--planting", default=DEFAULT_PLANTING, help="параметры посадки")
    parser.add_argument("--layers", default=DEFAULT_LAYERS, help="правила распознавания слоёв")
    parser.add_argument("--boundary-layer", help="слой с замкнутым контуром границы участка")
    parser.add_argument("--override", action="append", default=[], type=_override_arg,
                        metavar="СЛОЙ=ТИП", help="задать тип слоя вручную, можно несколько раз")
    args = parser.parse_args(argv)

    try:
        result = run(args.input, args.output, args.species, args.rules, args.planting, args.json,
                     args.layers, dict(args.override), args.boundary_layer)
    except AreaTooLarge as error:
        print(f"Ошибка: {error} Укажите слой границы: --boundary-layer СЛОЙ", file=sys.stderr)
        return 2
    except ValueError as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 2

    site = result.site
    trees = sum(p.species_type == "tree" for p in result.placements)
    shrubs = sum(p.species_type == "shrub" for p in result.placements)
    area = f"{site.boundary.area:,.0f}".replace(",", " ")
    print(f"Граница: {BOUNDARY_LABELS.get(site.boundary_method, site.boundary_method)}, {area} м²")
    print(f"Объектов учтено: {len(site.parsed.features)}, слоёв без типа: {len(site.parsed.unresolved_layers)}")
    print(f"Посадок: деревья {trees}, кустарники {shrubs}; отклонено {len(result.rejections)}")
    if result.greening is not None:
        lawn = f"{result.greening.lawn_area_m2:,.0f}".replace(",", " ")
        print(f"Газоны {lawn} м², живые изгороди {result.greening.hedge_length_m:.0f} м, "
              f"цветники {len(result.greening.flowerbeds)}")
    print(f"DXF: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
