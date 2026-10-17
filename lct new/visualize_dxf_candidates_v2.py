import argparse
import csv
import math
import re
from pathlib import Path

import ezdxf
import matplotlib.pyplot as plt


TARGET_LAYERS = {"0", "ТРУБЫ_НО"}
LENGTH_RE = re.compile(r"L\s*=\s*([0-9]+(?:[.,][0-9]+)?)\s*(?:м|m)?", re.IGNORECASE)
ATTR_RE = re.compile(r"ДЛИНА", re.IGNORECASE)


def entity_points(entity):
    kind = entity.dxftype()
    try:
        if kind == "LINE":
            return [(entity.dxf.start.x, entity.dxf.start.y),
                    (entity.dxf.end.x, entity.dxf.end.y)]
        if kind == "LWPOLYLINE":
            return [(p[0], p[1]) for p in entity.get_points()]
        if kind == "POLYLINE":
            return [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
        if kind == "ARC":
            cx, cy = entity.dxf.center.x, entity.dxf.center.y
            r = entity.dxf.radius
            start, end = math.radians(entity.dxf.start_angle), math.radians(entity.dxf.end_angle)
            while end < start:
                end += 2 * math.pi
            n = max(12, int((end - start) * 24))
            return [(cx + r * math.cos(start + (end - start) * i / n),
                     cy + r * math.sin(start + (end - start) * i / n)) for i in range(n + 1)]
        if kind == "CIRCLE":
            cx, cy = entity.dxf.center.x, entity.dxf.center.y
            r = entity.dxf.radius
            return [(cx + r * math.cos(2 * math.pi * i / 48),
                     cy + r * math.sin(2 * math.pi * i / 48)) for i in range(49)]
    except Exception:
        return []
    return []


def length_of_points(points, closed=False):
    if len(points) < 2:
        return 0.0
    total = sum(math.hypot(points[i + 1][0] - points[i][0],
                           points[i + 1][1] - points[i][1])
                for i in range(len(points) - 1))
    if closed and len(points) > 2:
        total += math.hypot(points[0][0] - points[-1][0],
                            points[0][1] - points[-1][1])
    return total


def entity_length(entity):
    kind = entity.dxftype()
    try:
        if kind == "LINE":
            return math.dist((entity.dxf.start.x, entity.dxf.start.y),
                             (entity.dxf.end.x, entity.dxf.end.y))
        if kind in {"LWPOLYLINE", "POLYLINE"}:
            pts = entity_points(entity)
            closed = bool(entity.closed) if kind == "LWPOLYLINE" else bool(entity.is_closed)
            return length_of_points(pts, closed)
        if kind == "ARC":
            a1, a2 = entity.dxf.start_angle, entity.dxf.end_angle
            delta = (a2 - a1) % 360
            return math.radians(delta) * entity.dxf.radius
        if kind == "CIRCLE":
            return 2 * math.pi * entity.dxf.radius
    except Exception:
        return None
    return None


def parse_number(value):
    try:
        return float(str(value).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def get_block_info(insert):
    values = []
    try:
        for att in insert.attribs:
            tag = str(att.dxf.tag)
            value = str(att.dxf.text)
            if ATTR_RE.search(tag) or ATTR_RE.search(value):
                number = parse_number(value)
                if number is not None:
                    values.append((number, f"{tag}={value}"))
    except Exception:
        pass
    return values


def get_text_lengths(entities):
    values = []
    for e in entities:
        if e.dxftype() in {"TEXT", "ATTRIB", "ATTDEF", "MTEXT"}:
            try:
                content = e.dxf.text if e.dxftype() != "MTEXT" else e.text
                match = LENGTH_RE.search(str(content))
                if match:
                    number = parse_number(match.group(1))
                    if number is not None:
                        values.append((number, str(content).strip()))
            except Exception:
                pass
    return values


def virtual_entities_safe(insert):
    try:
        return list(insert.virtual_entities())
    except Exception:
        return []


def collect_candidates(doc, tolerance=0.015, min_abs_tol=0.25):
    msp = doc.modelspace()
    records = []
    block_count = 0
    for insert in msp.query("INSERT"):
        layer = str(insert.dxf.layer)
        if layer not in TARGET_LAYERS:
            continue
        block_count += 1
        entities = virtual_entities_safe(insert)
        targets = get_block_info(insert) + get_text_lengths(entities)
        candidates = []
        for e in entities:
            pts = entity_points(e)
            if len(pts) < 2:
                continue
            length = entity_length(e)
            if length is None:
                continue
            matches = [(target, label) for target, label in targets
                       if abs(length - target) <= max(min_abs_tol, abs(target) * tolerance)]
            if matches:
                best_target, best_label = min(matches, key=lambda item: abs(length - item[0]))
                candidates.append({
                    "layer": layer,
                    "block": str(insert.dxf.name),
                    "handle": str(e.dxf.handle) if e.dxf.hasattr("handle") else "",
                    "entity_type": e.dxftype(),
                    "length": length,
                    "matched_value": best_target,
                    "matched_label": best_label,
                    "points": pts,
                })
        records.extend(candidates)
    return block_count, records


def collect_background(doc):
    items = []
    for e in doc.modelspace():
        if e.dxftype() == "INSERT":
            continue
        pts = entity_points(e)
        if len(pts) >= 2:
            items.append((str(e.dxf.layer), pts))
    return items


def bounds(items):
    xs, ys = [], []
    for item in items:
        pts = item["points"] if isinstance(item, dict) else item[1]
        xs.extend(p[0] for p in pts)
        ys.extend(p[1] for p in pts)
    if not xs:
        return None
    return min(xs), max(xs), min(ys), max(ys)


def plot_group(records, background, layer, path, title, padding=0.15):
    selected = [r for r in records if r["layer"] == layer]
    if not selected:
        return False
    bg = bounds(background)
    sel = bounds(selected)
    if sel is None:
        return False
    minx, maxx, miny, maxy = sel
    width, height = maxx - minx, maxy - miny
    margin = max(width, height, 1.0) * padding + 1.0
    minx, maxx, miny, maxy = minx - margin, maxx + margin, miny - margin, maxy + margin

    fig, ax = plt.subplots(figsize=(12, 8))
    if bg:
        bx0, bx1, by0, by1 = bg
        # Show the full-drawing context only when it overlaps the zoom window.
        if not (bx1 < minx or bx0 > maxx or by1 < miny or by0 > maxy):
            for bg_layer, pts in background:
                px = [p[0] for p in pts]
                py = [p[1] for p in pts]
                if max(px) < minx or min(px) > maxx or max(py) < miny or min(py) > maxy:
                    continue
                ax.plot(px, py, color="0.82", linewidth=0.6, zorder=1)

    colors = {"0": "red", "ТРУБЫ_НО": "blue"}
    for idx, rec in enumerate(selected, 1):
        pts = rec["points"]
        px, py = [p[0] for p in pts], [p[1] for p in pts]
        ax.plot(px, py, color=colors.get(layer, "red"), linewidth=2.2, zorder=3)
        # Label at the midpoint; shorter labels avoid the previous unreadable pile-up.
        mid = pts[len(pts) // 2]
        label = f'{rec["block"]} | {rec["length"]:.2f} m'
        ax.annotate(label, (mid[0], mid[1]), xytext=(4, 4),
                    textcoords="offset points", fontsize=7, color=colors.get(layer, "red"),
                    alpha=0.9, zorder=4)
    ax.set_title(title)
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.grid(True, alpha=0.2)
    ax.set_aspect("equal", adjustable="datalim")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return True


def plot_overview(records, path):
    if not records:
        return
    fig, ax = plt.subplots(figsize=(12, 8))
    for layer, color in (("0", "red"), ("ТРУБЫ_НО", "blue")):
        selected = [r for r in records if r["layer"] == layer]
        for r in selected:
            pts = r["points"]
            ax.plot([p[0] for p in pts], [p[1] for p in pts],
                    color=color, linewidth=1.4, alpha=0.8)
    ax.set_title("Обзор всех линий-кандидатов: красный — слой 0; синий — ТРУБЫ_НО")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.grid(True, alpha=0.2)
    ax.set_aspect("equal", adjustable="datalim")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def write_csv(records, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["layer", "block", "entity_handle", "entity_type",
                         "length", "matched_value", "matched_label",
                         "start_x", "start_y", "end_x", "end_y"])
        for r in records:
            pts = r["points"]
            writer.writerow([
                r["layer"], r["block"], r["handle"], r["entity_type"],
                f'{r["length"]:.4f}', f'{r["matched_value"]:.4f}', r["matched_label"],
                f"{pts[0][0]:.4f}", f"{pts[0][1]:.4f}",
                f"{pts[-1][0]:.4f}", f"{pts[-1][1]:.4f}",
            ])


def main():
    parser = argparse.ArgumentParser(description="Увеличенная диагностика геометрии DXF без изменения исходного файла.")
    parser.add_argument("dxf", help="Путь к исходному DXF")
    parser.add_argument("--output-dir", default="data/debug_visualization_v2", help="Папка для PNG и CSV")
    parser.add_argument("--background", action="store_true", help="Добавить обычную геометрию чертежа на фон")
    parser.add_argument("--tolerance", type=float, default=0.015, help="Относительный допуск совпадения длин")
    parser.add_argument("--min-abs-tol", type=float, default=0.25, help="Минимальный абсолютный допуск")
    args = parser.parse_args()

    dxf_path = Path(args.dxf)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = ezdxf.readfile(dxf_path)
    block_count, records = collect_candidates(doc, args.tolerance, args.min_abs_tol)
    background = collect_background(doc) if args.background else []

    plot_overview(records, out_dir / "00_overview.png")
    made = []
    for layer, filename, title in [
        ("0", "01_layer_0_zoom.png", "Увеличение кандидатов слоя 0"),
        ("ТРУБЫ_НО", "02_pipes_no_zoom.png", "Увеличение кандидатов ТРУБЫ_НО"),
    ]:
        if plot_group(records, background, layer, out_dir / filename, title):
            made.append(filename)

    write_csv(records, out_dir / "candidate_lines_v2.csv")
    print(f"Блоков на слоях 0 и ТРУБЫ_НО: {block_count}")
    print(f"Найдено линий-кандидатов: {len(records)}")
    print(f"PNG: {out_dir / '00_overview.png'}")
    for name in made:
        print(f"PNG: {out_dir / name}")
    print(f"CSV: {out_dir / 'candidate_lines_v2.csv'}")
    if not args.background:
        print("Для фона из обычной геометрии запусти повторно с флагом --background.")
    print("Это диагностические кандидаты, не подтверждённые трассы.")


if __name__ == "__main__":
    main()
