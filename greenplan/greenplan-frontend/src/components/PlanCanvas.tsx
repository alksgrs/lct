import { Maximize2, Minus, Plus } from "lucide-react";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { FALLBACK_STYLE, KIND_GROUP, KIND_STYLE, TIGHT_MARGIN_M, marginTone, num, type LayerGroup } from "../format";
import { boundsOf, lines, niceStep, points, polygons, type Bounds } from "../geometry";
import type { Check, Feature, Geometry, Greening, Placement, Position, Rejection, Rule, Species } from "../types";

export type Mode = "view" | "move" | "add-tree" | "add-shrub";

export interface Visibility {
  tree: boolean;
  shrub: boolean;
  rejections: boolean;
  tight: boolean;
  lawn: boolean;
  scene: boolean;
  groups: Record<LayerGroup, boolean>;
}

interface Props {
  features: Feature[];
  site: Geometry | null;
  greening: Greening | null;
  placements: Placement[];
  rejections: Rejection[];
  rejectionRule: string | null;
  visibility: Visibility;
  selectedId: string | null;
  checks: Check[] | null;
  rulesById: Record<string, Rule>;
  issueIds: Set<string>;
  mode: Mode;
  focus: { x: number; y: number; nonce: number } | null;
  onSelect: (id: string | null) => void;
  onDragStart: (id: string) => void;
  onDrag: (id: string, x: number, y: number) => void;
  onDragEnd: (id: string, x: number, y: number) => void;
  onAdd: (species: Species, x: number, y: number) => void;
}

interface KindLayer {
  kind: string;
  group: LayerGroup;
  stroke: Path2D;
  fill: Path2D | null;
  dots: Position[];
}

interface View {
  cx: number;
  cy: number;
  scale: number;
}

type Drag =
  | { type: "pan"; sx: number; sy: number; cx: number; cy: number; moved: boolean }
  | { type: "point"; id: string; sx: number; sy: number; moved: boolean };

const RADIUS_M: Record<Species, number> = { tree: 1.0, shrub: 0.5 };
const MIN_RADIUS_PX: Record<Species, number> = { tree: 2.6, shrub: 1.7 };
const CELL_M = 4;
const MAX_SCALE = 240;
const FOCUS_SCALE = 14;

const TOKENS = [
  "--map-bg", "--map-site", "--map-site-line", "--tree", "--tree-line", "--shrub", "--shrub-line",
  "--stop", "--tight", "--ok", "--accent", "--ink", "--ink-2", "--ink-3", "--panel", "--rule",
  "--k-building", "--k-building-fill", "--k-maf", "--k-road", "--k-pavement", "--k-water", "--k-sewer",
  "--k-drain", "--k-gas", "--k-heat", "--k-cable", "--k-power", "--k-light", "--k-green",
  "--k-green-fill", "--k-other", "--lawn", "--hedge", "--flower", "--flower-line",
];

function readPalette(element: Element): Record<string, string> {
  const style = getComputedStyle(element);
  const palette: Record<string, string> = {};
  for (const token of TOKENS) palette[token] = style.getPropertyValue(token).trim() || "#888";
  return palette;
}

function buildLayers(features: Feature[], origin: { x: number; y: number }): KindLayer[] {
  const byKind = new Map<string, KindLayer>();
  for (const feature of features) {
    let layer = byKind.get(feature.kind);
    if (!layer) {
      const style = KIND_STYLE[feature.kind] ?? FALLBACK_STYLE;
      layer = {
        kind: feature.kind,
        group: KIND_GROUP[feature.kind] ?? "other",
        stroke: new Path2D(),
        fill: style.fill ? new Path2D() : null,
        dots: [],
      };
      byKind.set(feature.kind, layer);
    }
    for (const line of lines(feature.geometry)) {
      line.forEach(([x, y], index) => {
        if (index === 0) layer!.stroke.moveTo(x - origin.x, y - origin.y);
        else layer!.stroke.lineTo(x - origin.x, y - origin.y);
      });
    }
    if (layer.fill) {
      for (const polygon of polygons(feature.geometry)) {
        for (const ring of polygon) {
          ring.forEach(([x, y], index) => {
            if (index === 0) layer!.fill!.moveTo(x - origin.x, y - origin.y);
            else layer!.fill!.lineTo(x - origin.x, y - origin.y);
          });
          layer.fill.closePath();
        }
      }
    }
    layer.dots.push(...points(feature.geometry));
  }
  const order = ["EXISTING_GREEN", "PAVEMENT", "ROAD", "TRAM_TRACK", "BUILDING", "MAF", "RETAINING_WALL"];
  return [...byKind.values()].sort((a, b) => {
    const ia = order.indexOf(a.kind);
    const ib = order.indexOf(b.kind);
    return (ia === -1 ? order.length : ia) - (ib === -1 ? order.length : ib);
  });
}

function buildSite(site: Geometry | null, origin: { x: number; y: number }): Path2D {
  const path = new Path2D();
  for (const polygon of polygons(site)) {
    for (const ring of polygon) {
      ring.forEach(([x, y], index) => {
        if (index === 0) path.moveTo(x - origin.x, y - origin.y);
        else path.lineTo(x - origin.x, y - origin.y);
      });
      path.closePath();
    }
  }
  return path;
}

function buildGrid(placements: Placement[]): Map<string, Placement[]> {
  const grid = new Map<string, Placement[]>();
  for (const placement of placements) {
    const key = `${Math.floor(placement.x / CELL_M)}:${Math.floor(placement.y / CELL_M)}`;
    const cell = grid.get(key);
    if (cell) cell.push(placement);
    else grid.set(key, [placement]);
  }
  return grid;
}

function buildHedges(greening: Greening | null, origin: { x: number; y: number }): Path2D {
  const path = new Path2D();
  for (const hedge of greening?.hedges ?? []) {
    hedge.coordinates.forEach(([x, y], index) => {
      if (index === 0) path.moveTo(x - origin.x, y - origin.y);
      else path.lineTo(x - origin.x, y - origin.y);
    });
  }
  return path;
}

function buildBeds(greening: Greening | null, origin: { x: number; y: number }): Path2D {
  const path = new Path2D();
  for (const bed of greening?.flowerbeds ?? []) {
    const x = bed.x - origin.x;
    const y = bed.y - origin.y;
    path.moveTo(x + bed.radius_m, y);
    path.arc(x, y, bed.radius_m, 0, Math.PI * 2);
  }
  return path;
}

function dimensionLabel(check: Check, rule: Rule | undefined): string {
  const distance = check.distance_m ?? 0;
  if (!rule || rule.kind === "not_regulated" || rule.limit_m === null) return `${num(distance, 2)} м`;
  const sign = distance < rule.limit_m ? "<" : "≥";
  return `${num(distance, 2)} ${sign} ${num(rule.limit_m, 1)} м`;
}

export default function PlanCanvas(props: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const coordsRef = useRef<HTMLSpanElement>(null);
  const propsRef = useRef(props);
  const viewRef = useRef<View>({ cx: 0, cy: 0, scale: 1 });
  const sizeRef = useRef({ w: 0, h: 0, dpr: 1 });
  const fittedRef = useRef(false);
  const dragRef = useRef<Drag | null>(null);
  const frameRef = useRef(0);
  const [hud, setHud] = useState({ barPx: 0, barLabel: "" });
  const [hover, setHover] = useState(false);

  propsRef.current = props;

  const bounds: Bounds = useMemo(() => {
    return (
      boundsOf([props.site]) ??
      boundsOf(props.features.map((f) => f.geometry), props.placements) ?? { minX: 0, minY: 0, maxX: 100, maxY: 100 }
    );
  }, [props.site, props.features]);

  const origin = useMemo(() => ({ x: bounds.minX, y: bounds.minY }), [bounds]);
  const layers = useMemo(() => buildLayers(props.features, origin), [props.features, origin]);
  const sitePath = useMemo(() => buildSite(props.site, origin), [props.site, origin]);
  const lawnPath = useMemo(() => buildSite(props.greening?.lawn ?? null, origin), [props.greening, origin]);
  const hedgePath = useMemo(() => buildHedges(props.greening, origin), [props.greening, origin]);
  const bedPath = useMemo(() => buildBeds(props.greening, origin), [props.greening, origin]);
  const grid = useMemo(() => buildGrid(props.placements), [props.placements]);
  const byId = useMemo(() => new Map(props.placements.map((p) => [p.id, p])), [props.placements]);

  const fitScale = useCallback(() => {
    const { w, h } = sizeRef.current;
    const width = Math.max(bounds.maxX - bounds.minX, 1);
    const height = Math.max(bounds.maxY - bounds.minY, 1);
    return Math.min(w / (width * 1.08), h / (height * 1.08));
  }, [bounds]);

  const fit = useCallback(() => {
    viewRef.current = {
      cx: (bounds.minX + bounds.maxX) / 2,
      cy: (bounds.minY + bounds.maxY) / 2,
      scale: fitScale(),
    };
  }, [bounds, fitScale]);

  const toScreen = (x: number, y: number) => {
    const { w, h } = sizeRef.current;
    const v = viewRef.current;
    return [(x - v.cx) * v.scale + w / 2, h / 2 - (y - v.cy) * v.scale] as const;
  };

  const toWorld = (sx: number, sy: number) => {
    const { w, h } = sizeRef.current;
    const v = viewRef.current;
    return { x: (sx - w / 2) / v.scale + v.cx, y: (h / 2 - sy) / v.scale + v.cy };
  };

  const draw = useCallback(() => {
    frameRef.current = 0;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const p = propsRef.current;
    const { w, h, dpr } = sizeRef.current;
    const v = viewRef.current;
    const c = readPalette(canvas);
    const px = 1 / v.scale;

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = c["--map-bg"];
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.setTransform(
      dpr * v.scale, 0, 0, -dpr * v.scale,
      dpr * (w / 2 - (v.cx - origin.x) * v.scale),
      dpr * (h / 2 + (v.cy - origin.y) * v.scale),
    );

    ctx.fillStyle = c["--map-site"];
    ctx.fill(sitePath, "evenodd");

    if (p.visibility.lawn) {
      ctx.fillStyle = c["--lawn"];
      ctx.fill(lawnPath, "evenodd");
    }

    for (const layer of layers) {
      if (!p.visibility.groups[layer.group] || !layer.fill) continue;
      const style = KIND_STYLE[layer.kind] ?? FALLBACK_STYLE;
      ctx.fillStyle = c[style.fill ?? style.token];
      ctx.fill(layer.fill, "evenodd");
    }
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    for (const layer of layers) {
      if (!p.visibility.groups[layer.group]) continue;
      const style = KIND_STYLE[layer.kind] ?? FALLBACK_STYLE;
      ctx.strokeStyle = c[style.token];
      ctx.lineWidth = style.width * px;
      ctx.setLineDash(style.dash ? style.dash.map((d) => d * px) : []);
      ctx.stroke(layer.stroke);
    }

    ctx.strokeStyle = c["--map-site-line"];
    ctx.lineWidth = 1.5 * px;
    ctx.setLineDash([7 * px, 4 * px]);
    ctx.stroke(sitePath);
    ctx.setLineDash([]);

    if (p.visibility.scene) {
      ctx.strokeStyle = c["--hedge"];
      ctx.lineWidth = Math.max(0.8, 2.5 * px);
      ctx.stroke(hedgePath);
      ctx.fillStyle = c["--flower"];
      ctx.fill(bedPath);
      ctx.strokeStyle = c["--flower-line"];
      ctx.lineWidth = 1.2 * px;
      ctx.stroke(bedPath);
    }

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const inView = (sx: number, sy: number, pad: number) => sx > -pad && sy > -pad && sx < w + pad && sy < h + pad;

    for (const layer of layers) {
      if (!p.visibility.groups[layer.group] || layer.dots.length === 0) continue;
      const style = KIND_STYLE[layer.kind] ?? FALLBACK_STYLE;
      ctx.strokeStyle = c[style.token];
      ctx.fillStyle = c[style.token];
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (const [x, y] of layer.dots) {
        const [sx, sy] = toScreen(x, y);
        if (!inView(sx, sy, 8)) continue;
        if (layer.kind === "LIGHTING") {
          ctx.moveTo(sx + 3.5, sy);
          ctx.arc(sx, sy, 3.5, 0, Math.PI * 2);
          ctx.moveTo(sx - 2.5, sy - 2.5);
          ctx.lineTo(sx + 2.5, sy + 2.5);
          ctx.moveTo(sx + 2.5, sy - 2.5);
          ctx.lineTo(sx - 2.5, sy + 2.5);
        } else if (layer.kind === "BIN") {
          ctx.rect(sx - 2.5, sy - 2.5, 5, 5);
        } else {
          ctx.moveTo(sx + 2.5, sy);
          ctx.arc(sx, sy, 2.5, 0, Math.PI * 2);
        }
      }
      ctx.stroke();
    }

    if (p.visibility.rejections) {
      ctx.strokeStyle = c["--stop"];
      ctx.globalAlpha = 0.7;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      for (const r of p.rejections) {
        if (p.rejectionRule && r.rule_id !== p.rejectionRule) continue;
        const [sx, sy] = toScreen(r.x, r.y);
        if (!inView(sx, sy, 4)) continue;
        ctx.moveTo(sx - 2.5, sy - 2.5);
        ctx.lineTo(sx + 2.5, sy + 2.5);
        ctx.moveTo(sx + 2.5, sy - 2.5);
        ctx.lineTo(sx - 2.5, sy + 2.5);
      }
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    const radius = (species: Species) =>
      Math.max(RADIUS_M[species] * v.scale, Math.min(MIN_RADIUS_PX[species], Math.max(1, (MIN_RADIUS_PX[species] * v.scale) / 3)));

    for (const species of ["shrub", "tree"] as Species[]) {
      if (!p.visibility[species]) continue;
      const r = radius(species);
      ctx.beginPath();
      for (const placement of p.placements) {
        if (placement.species_type !== species) continue;
        const [sx, sy] = toScreen(placement.x, placement.y);
        if (!inView(sx, sy, r)) continue;
        ctx.moveTo(sx + r, sy);
        ctx.arc(sx, sy, r, 0, Math.PI * 2);
      }
      ctx.fillStyle = c[species === "tree" ? "--tree" : "--shrub"];
      ctx.fill();
      if (r > 3) {
        ctx.strokeStyle = c[species === "tree" ? "--tree-line" : "--shrub-line"];
        ctx.lineWidth = 1;
        ctx.stroke();
      }
    }

    if (p.visibility.tight) {
      ctx.strokeStyle = c["--tight"];
      ctx.lineWidth = 1.6;
      ctx.beginPath();
      for (const placement of p.placements) {
        if (!p.visibility[placement.species_type]) continue;
        const margin = placement.tightest?.margin_m;
        if (margin === undefined || margin >= TIGHT_MARGIN_M) continue;
        const [sx, sy] = toScreen(placement.x, placement.y);
        const r = radius(placement.species_type) + 2.5;
        if (!inView(sx, sy, r)) continue;
        ctx.moveTo(sx + r, sy);
        ctx.arc(sx, sy, r, 0, Math.PI * 2);
      }
      ctx.stroke();
    }

    if (p.issueIds.size > 0) {
      ctx.strokeStyle = c["--stop"];
      ctx.lineWidth = 2;
      ctx.beginPath();
      for (const id of p.issueIds) {
        const placement = byId.get(id);
        if (!placement) continue;
        const [sx, sy] = toScreen(placement.x, placement.y);
        const r = radius(placement.species_type) + 3.5;
        ctx.moveTo(sx + r, sy);
        ctx.arc(sx, sy, r, 0, Math.PI * 2);
      }
      ctx.stroke();
    }

    const selected = p.selectedId ? byId.get(p.selectedId) : undefined;
    if (selected) {
      const [sx, sy] = toScreen(selected.x, selected.y);
      const r = radius(selected.species_type) + 5;

      if (p.checks) {
        const shown = p.checks
          .filter((check) => check.nearest && check.distance_m !== null && check.status !== "not_applicable")
          .filter((check) => {
            if (check.status === "violated" || check.status === "banned_zone") return true;
            const limit = p.rulesById[check.rule_id]?.limit_m ?? 0;
            return (check.distance_m ?? 0) <= Math.max(limit * 3, 12);
          })
          .sort((a, b) => (a.margin_m ?? 99) - (b.margin_m ?? 99))
          .slice(0, 6);

        ctx.font = '500 11px "IBM Plex Mono", ui-monospace, monospace';
        ctx.textBaseline = "middle";
        const placed: { x: number; y: number; w: number }[] = [];
        const overlaps = (x: number, y: number, w: number) =>
          placed.some((box) => Math.abs(box.x - x) < (box.w + w) / 2 + 4 && Math.abs(box.y - y) < 18);
        for (const check of shown) {
          const rule = p.rulesById[check.rule_id];
          const tone = rule?.kind === "not_regulated" ? "none" : marginTone(check.margin_m);
          const color = tone === "stop" ? c["--stop"] : tone === "tight" ? c["--tight"] : tone === "ok" ? c["--ink-2"] : c["--ink-3"];
          const [nx, ny] = toScreen(check.nearest![0], check.nearest![1]);
          const length = Math.hypot(nx - sx, ny - sy);
          if (length < 1) continue;
          const ux = (nx - sx) / length;
          const uy = (ny - sy) / length;

          ctx.strokeStyle = color;
          ctx.fillStyle = color;
          ctx.lineWidth = 1;
          ctx.setLineDash(rule?.kind === "not_regulated" ? [3, 3] : []);
          ctx.beginPath();
          ctx.moveTo(sx, sy);
          ctx.lineTo(nx, ny);
          ctx.stroke();
          ctx.setLineDash([]);
          ctx.beginPath();
          ctx.moveTo(nx - uy * 5, ny + ux * 5);
          ctx.lineTo(nx + uy * 5, ny - ux * 5);
          ctx.stroke();

          const label = dimensionLabel(check, rule);
          const tw = ctx.measureText(label).width;
          const offset = length < tw + 24 ? 16 : 0;
          const side = uy > 0 ? -1 : 1;
          let mx = (sx + nx) / 2 + (offset ? -uy * offset * side : 0);
          let my = (sy + ny) / 2 + (offset ? ux * offset * side : 0);
          for (let step = 1; step < 6 && overlaps(mx, my, tw + 8); step++) {
            my += 18 * (step % 2 === 1 ? step : -step);
          }
          placed.push({ x: mx, y: my, w: tw + 8 });
          ctx.fillStyle = c["--panel"];
          ctx.fillRect(mx - tw / 2 - 4, my - 8, tw + 8, 16);
          ctx.strokeStyle = color;
          ctx.strokeRect(mx - tw / 2 - 4 + 0.5, my - 8 + 0.5, tw + 7, 15);
          ctx.fillStyle = color;
          ctx.fillText(label, mx - tw / 2, my + 0.5);
        }
      }

      ctx.strokeStyle = c["--accent"];
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(sx, sy, r, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(sx - r - 6, sy);
      ctx.lineTo(sx - r + 2, sy);
      ctx.moveTo(sx + r - 2, sy);
      ctx.lineTo(sx + r + 6, sy);
      ctx.moveTo(sx, sy - r - 6);
      ctx.lineTo(sx, sy - r + 2);
      ctx.moveTo(sx, sy + r - 2);
      ctx.lineTo(sx, sy + r + 6);
      ctx.stroke();
    }

    const meters = niceStep(110 / v.scale);
    const barPx = meters * v.scale;
    const barLabel = meters >= 1000 ? `${num(meters / 1000)} км` : `${num(meters, meters < 1 ? 1 : 0)} м`;
    setHud((current) => (current.barLabel === barLabel && Math.abs(current.barPx - barPx) < 0.5 ? current : { barPx, barLabel }));
  }, [layers, sitePath, lawnPath, hedgePath, bedPath, origin, byId]);

  const schedule = useCallback(() => {
    if (!frameRef.current) frameRef.current = requestAnimationFrame(draw);
  }, [draw]);

  useLayoutEffect(() => {
    const wrap = wrapRef.current;
    const canvas = canvasRef.current;
    if (!wrap || !canvas) return;
    const observer = new ResizeObserver(() => {
      const rect = wrap.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      sizeRef.current = { w: rect.width, h: rect.height, dpr };
      canvas.width = Math.max(1, Math.round(rect.width * dpr));
      canvas.height = Math.max(1, Math.round(rect.height * dpr));
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
      if (!fittedRef.current && rect.width > 0) {
        fit();
        fittedRef.current = true;
      }
      schedule();
    });
    observer.observe(wrap);
    return () => observer.disconnect();
  }, [fit, schedule]);

  useEffect(() => {
    schedule();
  });

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const redraw = () => schedule();
    media.addEventListener("change", redraw);
    const observer = new MutationObserver(redraw);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => {
      media.removeEventListener("change", redraw);
      observer.disconnect();
    };
  }, [schedule]);

  useEffect(() => {
    if (!props.focus) return;
    const v = viewRef.current;
    viewRef.current = { cx: props.focus.x, cy: props.focus.y, scale: Math.max(v.scale, FOCUS_SCALE) };
    schedule();
  }, [props.focus, schedule]);

  const zoomBy = useCallback(
    (factor: number, sx?: number, sy?: number) => {
      const { w, h } = sizeRef.current;
      const ax = sx ?? w / 2;
      const ay = sy ?? h / 2;
      const before = toWorld(ax, ay);
      const v = viewRef.current;
      const min = fitScale() / 6;
      v.scale = Math.min(MAX_SCALE, Math.max(min, v.scale * factor));
      const after = toWorld(ax, ay);
      v.cx += before.x - after.x;
      v.cy += before.y - after.y;
      schedule();
    },
    [fitScale, schedule],
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      const rect = canvas.getBoundingClientRect();
      zoomBy(Math.exp(-event.deltaY * 0.0015), event.clientX - rect.left, event.clientY - rect.top);
    };
    canvas.addEventListener("wheel", onWheel, { passive: false });
    return () => canvas.removeEventListener("wheel", onWheel);
  }, [zoomBy]);

  const hitTest = (sx: number, sy: number): Placement | null => {
    const p = propsRef.current;
    const world = toWorld(sx, sy);
    const reach = Math.max(7 / viewRef.current.scale, 1.0);
    const x0 = Math.floor((world.x - reach) / CELL_M);
    const x1 = Math.floor((world.x + reach) / CELL_M);
    const y0 = Math.floor((world.y - reach) / CELL_M);
    const y1 = Math.floor((world.y + reach) / CELL_M);
    let best: Placement | null = null;
    let bestDistance = reach;
    for (let gx = x0; gx <= x1; gx++) {
      for (let gy = y0; gy <= y1; gy++) {
        for (const placement of grid.get(`${gx}:${gy}`) ?? []) {
          if (!p.visibility[placement.species_type]) continue;
          const d = Math.hypot(placement.x - world.x, placement.y - world.y);
          if (d <= bestDistance) {
            best = placement;
            bestDistance = d;
          }
        }
      }
    }
    return best;
  };

  const local = (event: React.PointerEvent) => {
    const rect = canvasRef.current!.getBoundingClientRect();
    return [event.clientX - rect.left, event.clientY - rect.top] as const;
  };

  const onPointerDown = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (event.button !== 0) return;
    const [sx, sy] = local(event);
    const p = propsRef.current;
    const hit = hitTest(sx, sy);
    event.currentTarget.setPointerCapture(event.pointerId);

    if (!hit && (p.mode === "add-tree" || p.mode === "add-shrub")) {
      const world = toWorld(sx, sy);
      p.onAdd(p.mode === "add-tree" ? "tree" : "shrub", world.x, world.y);
      return;
    }
    if (hit) {
      p.onSelect(hit.id);
      if (p.mode === "move") {
        dragRef.current = { type: "point", id: hit.id, sx, sy, moved: false };
        return;
      }
    }
    const v = viewRef.current;
    dragRef.current = { type: "pan", sx, sy, cx: v.cx, cy: v.cy, moved: Boolean(hit) };
  };

  const onPointerMove = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const [sx, sy] = local(event);
    const world = toWorld(sx, sy);
    if (coordsRef.current) coordsRef.current.textContent = `x ${num(world.x, 2)}   y ${num(world.y, 2)}`;
    const drag = dragRef.current;
    const p = propsRef.current;

    if (!drag) {
      const over = p.mode === "move" && hitTest(sx, sy) !== null;
      if (over !== hover) setHover(over);
      return;
    }
    if (drag.type === "point") {
      if (!drag.moved) {
        if (Math.hypot(sx - drag.sx, sy - drag.sy) < 2) return;
        drag.moved = true;
        p.onDragStart(drag.id);
      }
      p.onDrag(drag.id, world.x, world.y);
      return;
    }
    if (Math.hypot(sx - drag.sx, sy - drag.sy) > 3) drag.moved = true;
    const v = viewRef.current;
    v.cx = drag.cx - (sx - drag.sx) / v.scale;
    v.cy = drag.cy + (sy - drag.sy) / v.scale;
    schedule();
  };

  const onPointerUp = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const drag = dragRef.current;
    dragRef.current = null;
    if (!drag) return;
    const p = propsRef.current;
    if (drag.type === "point" && drag.moved) {
      const [sx, sy] = local(event);
      const world = toWorld(sx, sy);
      p.onDragEnd(drag.id, world.x, world.y);
    }
    if (drag.type === "pan" && !drag.moved) p.onSelect(null);
  };

  const cursor =
    props.mode === "add-tree" || props.mode === "add-shrub"
      ? "crosshair"
      : hover
        ? "grab"
        : "default";

  return (
    <div className="plan-canvas" ref={wrapRef}>
      <canvas
        ref={canvasRef}
        style={{ cursor }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={() => (dragRef.current = null)}
        onPointerLeave={() => coordsRef.current && (coordsRef.current.textContent = "")}
        onDoubleClick={(event) => {
          const rect = event.currentTarget.getBoundingClientRect();
          zoomBy(2, event.clientX - rect.left, event.clientY - rect.top);
        }}
      />
      <div className="plan-zoom">
        <button type="button" title="Приблизить" onClick={() => zoomBy(1.6)}>
          <Plus size={16} />
        </button>
        <button type="button" title="Отдалить" onClick={() => zoomBy(1 / 1.6)}>
          <Minus size={16} />
        </button>
        <button
          type="button"
          title="Весь участок"
          onClick={() => {
            fit();
            schedule();
          }}
        >
          <Maximize2 size={15} />
        </button>
      </div>
      <div className="plan-scale">
        <span className="plan-scale-bar" style={{ width: `${hud.barPx}px` }} />
        <span>{hud.barLabel}</span>
      </div>
      <span className="plan-coords" ref={coordsRef} />
    </div>
  );
}
