import type { Geometry, Position } from "./types";

export interface Bounds {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

export function eachPosition(geometry: Geometry | null | undefined, visit: (p: Position) => void): void {
  if (!geometry) return;
  switch (geometry.type) {
    case "Point":
      visit(geometry.coordinates);
      return;
    case "MultiPoint":
    case "LineString":
      geometry.coordinates.forEach(visit);
      return;
    case "MultiLineString":
    case "Polygon":
      geometry.coordinates.forEach((line) => line.forEach(visit));
      return;
    case "MultiPolygon":
      geometry.coordinates.forEach((polygon) => polygon.forEach((ring) => ring.forEach(visit)));
      return;
    case "GeometryCollection":
      geometry.geometries.forEach((part) => eachPosition(part, visit));
  }
}

export function boundsOf(geometries: (Geometry | null | undefined)[], extra: { x: number; y: number }[] = []): Bounds | null {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  const take = (x: number, y: number) => {
    if (x < minX) minX = x;
    if (y < minY) minY = y;
    if (x > maxX) maxX = x;
    if (y > maxY) maxY = y;
  };
  geometries.forEach((geometry) => eachPosition(geometry, ([x, y]) => take(x, y)));
  extra.forEach((p) => take(p.x, p.y));
  if (!Number.isFinite(minX)) return null;
  return { minX, minY, maxX, maxY };
}

export function polygons(geometry: Geometry | null | undefined): Position[][][] {
  if (!geometry) return [];
  if (geometry.type === "Polygon") return [geometry.coordinates];
  if (geometry.type === "MultiPolygon") return geometry.coordinates;
  if (geometry.type === "GeometryCollection") return geometry.geometries.flatMap(polygons);
  return [];
}

export function lines(geometry: Geometry | null | undefined): Position[][] {
  if (!geometry) return [];
  switch (geometry.type) {
    case "LineString":
      return [geometry.coordinates];
    case "MultiLineString":
      return geometry.coordinates;
    case "Polygon":
      return geometry.coordinates;
    case "MultiPolygon":
      return geometry.coordinates.flat();
    case "GeometryCollection":
      return geometry.geometries.flatMap(lines);
    default:
      return [];
  }
}

export function points(geometry: Geometry | null | undefined): Position[] {
  if (!geometry) return [];
  if (geometry.type === "Point") return [geometry.coordinates];
  if (geometry.type === "MultiPoint") return geometry.coordinates;
  if (geometry.type === "GeometryCollection") return geometry.geometries.flatMap(points);
  return [];
}

export function niceStep(target: number): number {
  const power = Math.pow(10, Math.floor(Math.log10(target)));
  const base = target / power;
  const nice = base >= 5 ? 5 : base >= 2 ? 2 : 1;
  return nice * power;
}
