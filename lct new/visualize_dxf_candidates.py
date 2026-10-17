import argparse
import math
import re
from pathlib import Path

import ezdxf
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D


TARGET_LAYERS = {"0", "ТРУБЫ_НО"}
LABEL_RE = re.compile(r"L\s*=\s*([0-9]+(?:[.,][0-9]+)?)", re.IGNORECASE)


def safe_float(value):
    if value is None:
        return None
    try:
        return float(str(value).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def entity_length(entity):
    kind = entity.dxftype()
    try:
        if kind == "LINE":
            a, b = entity.dxf.start, entity.dxf.end
            return math.hypot(b.x - a.x, b.y - a.y)
        if kind == "LWPOLYLINE":
            pts = list(entity.get_points("xy"))
            if len(pts) < 2:
                return 0.0
            total = sum(math.hypot(pts[i][0] - pts[i-1][0],
                                   pts[i][1] - pts[i-1][1])
                        for i in range(1, len(pts)))
            if entity.closed:
                total += math.hypot(pts[0][0] - pts[-1][0],
                                    pts[0][1] - pts[-1][1])
            return total
    except Exception:
        return None
    return None


def get_xy(entity):
    kind = entity.dxftype()
    try:
        if kind == "LINE":
            a, b = entity.dxf.start, entity.dxf.end
            return [(a.x, a.y), (b.x, b.y)]
        if kind == "LWPOLYLINE":
            return [(p[0], p[1]) for p in entity.get_points("xy")]
        if kind == "POLYLINE":
            return [(v.dxf.location.x, v.dxf.location.y)
                    for v in entity.vertices]
    except Exception:
        return []
    return []


def draw_entity(ax, entity, color, linewidth, alpha=1.0):
    kind = entity.dxftype()
    try:
        if kind in {"LINE", "LWPOLYLINE", "POLYLINE"}:
            pts = get_xy(entity)
            if len(pts) >= 2:
                if kind == "LWPOLYLINE" and entity.closed:
                    pts = pts + [pts[0]]
                elif kind == "POLYLINE" and entity.is_closed:
                    pts = pts + [pts[0]]
                xs, ys = zip(*pts)
                ax.plot(xs, ys, color=color, linewidth=linewidth, alpha=alpha)
        elif kind == "CIRCLE":
            c = entity.dxf.center
            circle = plt.Circle((c.x, c.y), entity.dxf.radius,
                                fill=False, color=color,
                                linewidth=linewidth, alpha=alpha)
            ax.add_patch(circle)
        elif kind == "ARC":
            c = entity.dxf.center
            radius = entity.dxf.radius
            start = math.radians(entity.dxf.start_angle)
            end = math.radians(entity.dxf.end_angle)
            if end < start:
                end += 2 * math.pi
            steps = max(12, int((end - start) * 24))
            pts = [(c.x + radius * math.cos(t), c.y + radius * math.sin(t))
                   for t in [start + (end-start)*i/steps for i in range(steps+1)]]
            xs, ys = zip(*pts)
            ax.plot(xs, ys, color=color, linewidth=linewidth, alpha=alpha)
    except Exception:
        pass


def collect_insert_data(insert):
    attrs = {}
    for attrib in getattr(insert, "attribs", []):
        try:
            attrs[str(attrib.dxf.tag).upper()] = str(attrib.dxf.text)
        except Exception:
            pass

    attr_lengths = {
        tag: val for tag, raw in attrs.items()
        if "ДЛИНА" in tag and (val := safe_float(raw)) is not None
    }

    virtual = []
    texts = []
    try:
        for ent in insert.virtual_entities():
            virtual.append(ent)
            if ent.dxftype() in {"TEXT", "MTEXT", "ATTRIB"}:
                try:
                    text = ent.dxf.text if ent.dxftype() != "MTEXT" else ent.text
                    texts.append(str(text))
                except Exception:
                    pass
    except Exception:
        pass

    # ATTRIBs are sometimes not returned by virtual_entities().
    texts.extend(attrs.values())
    label_lengths = []
    for text in texts:
        for match in LABEL_RE.finditer(text.replace("\\P", " ")):
            val = safe_float(match.group(1))
            if val is not None:
                label_lengths.append(val)

    targets = list(attr_lengths.values()) + label_lengths
    candidates = []
    for ent in virtual:
        if ent.dxftype() != "LINE":
            continue
        length = entity_length(ent)
        if length is None:
            continue
        matches = [target for target in targets
                   if abs(length-target) <= max(0.25, target * 0.015)]
        if matches:
            candidates.append((ent, length, matches))

    return virtual, attrs, attr_lengths, label_lengths, candidates


def main():
    parser = argparse.ArgumentParser(
        description="Локальная визуализация DXF и линий-кандидатов из блоков."
    )
    parser.add_argument("input", help="Путь к исходному DXF")
    parser.add_argument("--output-dir", default="dxf_visual_debug",
                        help="Папка для PNG и CSV")
    parser.add_argument("--all-background", action="store_true",
                        help="Добавить геометрию чертежа на задний план (может быть медленнее)")
    args = parser.parse_args()

    source = Path(args.input)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = ezdxf.readfile(source)
    msp = doc.modelspace()

    records = []
    block_geometries = []
    candidate_segments = []
    all_x, all_y = [], []

    # Optional background: render basic top-level geometry in pale grey.
    if args.all_background:
        for ent in msp:
            if ent.dxftype() == "INSERT":
                try:
                    for child in ent.virtual_entities():
                        pts = get_xy(child)
                        if pts:
                            block_geometries.append(("background", child, None))
                            all_x.extend(p[0] for p in pts)
                            all_y.extend(p[1] for p in pts)
                except Exception:
                    continue
            else:
                pts = get_xy(ent)
                if pts:
                    block_geometries.append(("background", ent, None))
                    all_x.extend(p[0] for p in pts)
                    all_y.extend(p[1] for p in pts)

    target_inserts = [
        ent for ent in msp.query("INSERT")
        if str(ent.dxf.layer).upper() in {x.upper() for x in TARGET_LAYERS}
    ]

    for insert in target_inserts:
        layer = str(insert.dxf.layer)
        block_name = str(insert.dxf.name)
        virtual, attrs, attr_lengths, label_lengths, candidates = collect_insert_data(insert)
        ip = insert.dxf.insert
        for ent in virtual:
            pts = get_xy(ent)
            if pts:
                block_geometries.append(("target", ent, layer))
                all_x.extend(p[0] for p in pts)
                all_y.extend(p[1] for p in pts)
        for ent, length, matches in candidates:
            pts = get_xy(ent)
            if len(pts) >= 2:
                candidate_segments.append((pts[0], pts[-1], layer, block_name, length, matches))
                all_x.extend([pts[0][0], pts[-1][0]])
                all_y.extend([pts[0][1], pts[-1][1]])
        records.append({
            "layer": layer,
            "block": block_name,
            "insert_x": float(ip.x),
            "insert_y": float(ip.y),
            "attributes": attrs,
            "attr_lengths": attr_lengths,
            "label_lengths": label_lengths,
            "candidate_lengths": [round(c[1], 3) for c in candidates],
            "candidate_count": len(candidates),
        })

    if not all_x or not all_y:
        raise SystemExit("Не удалось найти геометрию для изображения.")

    fig, ax = plt.subplots(figsize=(14, 10))
    for category, ent, layer in block_geometries:
        if category == "background":
            draw_entity(ax, ent, color="#d0d0d0", linewidth=0.45, alpha=0.7)
        else:
            draw_entity(ax, ent, color="#8b969e", linewidth=0.7, alpha=0.85)

    colors = {"0": "#d62728", "ТРУБЫ_НО": "#1769aa"}
    for a, b, layer, block, length, matches in candidate_segments:
        color = colors.get(layer.upper(), "#d62728")
        ax.plot([a[0], b[0]], [a[1], b[1]], color=color, linewidth=2.8, zorder=5)
        mx, my = (a[0]+b[0])/2, (a[1]+b[1])/2
        ax.annotate(f"{block}\\n{length:.2f} м", (mx, my), fontsize=7,
                    color=color, xytext=(3, 3), textcoords="offset points",
                    zorder=6)

    span_x = max(all_x) - min(all_x)
    span_y = max(all_y) - min(all_y)
    pad_x = max(span_x * 0.04, 1)
    pad_y = max(span_y * 0.04, 1)
    ax.set_xlim(min(all_x)-pad_x, max(all_x)+pad_x)
    ax.set_ylim(min(all_y)-pad_y, max(all_y)+pad_y)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, linewidth=0.3, alpha=0.35)
    ax.set_title(f"DXF: {source.name}\\nКрасный — кандидаты со слоя 0; синий — ТРУБЫ_НО")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    legend = [
        Line2D([0], [0], color="#d62728", lw=2.8, label="Слой 0: кандидат"),
        Line2D([0], [0], color="#1769aa", lw=2.8, label="ТРУБЫ_НО: кандидат"),
        Line2D([0], [0], color="#8b969e", lw=1, label="Остальная геометрия выбранных блоков"),
    ]
    if args.all_background:
        legend.append(Line2D([0], [0], color="#d0d0d0", lw=1, label="Фон чертежа"))
    ax.legend(handles=legend, loc="best")
    png_path = out_dir / "dxf_candidates.png"
    fig.tight_layout()
    fig.savefig(png_path, dpi=180)
    plt.close(fig)

    csv_path = out_dir / "candidate_lines.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        f.write("layer,block,x1,y1,x2,y2,length_m,matched_values\\n")
        for a, b, layer, block, length, matches in candidate_segments:
            f.write(f'"{layer}","{block}",{a[0]:.3f},{a[1]:.3f},'
                    f'{b[0]:.3f},{b[1]:.3f},{length:.3f},'
                    f'"{";".join(f"{v:g}" for v in matches)}"\\n')

    print(f"PNG: {png_path.resolve()}")
    print(f"CSV: {csv_path.resolve()}")
    print(f"Блоков на слоях 0 и ТРУБЫ_НО: {len(records)}")
    print(f"Найдено линий-кандидатов: {len(candidate_segments)}")
    print("Это диагностические кандидаты, не подтверждённые трассы.")
    print("Если фон слишком большой, запускай без --all-background;")
    print("если на картинке пусто, попробуй --all-background.")


if __name__ == "__main__":
    main()
