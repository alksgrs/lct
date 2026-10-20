import { OrbitControls } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import { useLayoutEffect, useMemo, useRef } from "react";
import * as THREE from "three";

import { KIND_GROUP } from "../format";
import { boundsOf, lines, polygons } from "../geometry";
import type { Feature, Geometry, Greening, Placement } from "../types";

interface Props {
  features: Feature[];
  site: Geometry | null;
  placements: Placement[];
  greening?: Greening | null;
}

interface Origin {
  x: number;
  y: number;
}

const BUILDING_HEIGHT_M = 9;
const LINE_COLORS: Record<string, string> = {
  roads: "#8d9196",
  networks: "#5f6fa3",
  power: "#a0466e",
  green: "#7d9a5a",
  other: "#8a8578",
  buildings: "#6d675c",
};

function hash(text: string, salt: number): number {
  let h = 2166136261 ^ salt;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return ((h >>> 0) % 1000) / 1000;
}

function cssColor(token: string, fallback: string): string {
  const value = getComputedStyle(document.documentElement).getPropertyValue(token).trim();
  return value || fallback;
}

function Trees({ items, origin }: { items: Placement[]; origin: Origin }) {
  const trunks = useRef<THREE.InstancedMesh>(null);
  const crowns = useRef<THREE.InstancedMesh>(null);

  useLayoutEffect(() => {
    if (!trunks.current || !crowns.current) return;
    const matrix = new THREE.Matrix4();
    const rotation = new THREE.Quaternion();
    const position = new THREE.Vector3();
    const scale = new THREE.Vector3();
    const color = new THREE.Color();
    items.forEach((tree, index) => {
      const height = 2.6 + hash(tree.id, 1) * 1.4;
      const crown = 1.5 + hash(tree.id, 2) * 0.9;
      const x = tree.x - origin.x;
      const z = -(tree.y - origin.y);
      position.set(x, height / 2, z);
      scale.set(1, height, 1);
      trunks.current!.setMatrixAt(index, matrix.compose(position, rotation, scale));
      position.set(x, height + crown * 0.55, z);
      scale.set(crown, crown * 1.15, crown);
      crowns.current!.setMatrixAt(index, matrix.compose(position, rotation, scale));
      color.setHSL(0.31 + hash(tree.id, 3) * 0.05, 0.38, 0.3 + hash(tree.id, 4) * 0.08);
      crowns.current!.setColorAt(index, color);
    });
    trunks.current.instanceMatrix.needsUpdate = true;
    crowns.current.instanceMatrix.needsUpdate = true;
    if (crowns.current.instanceColor) crowns.current.instanceColor.needsUpdate = true;
  }, [items, origin]);

  if (items.length === 0) return null;
  return (
    <group>
      <instancedMesh key={`t${items.length}`} ref={trunks} args={[undefined, undefined, items.length]}>
        <cylinderGeometry args={[0.11, 0.16, 1, 6]} />
        <meshLambertMaterial color="#6e5644" />
      </instancedMesh>
      <instancedMesh key={`c${items.length}`} ref={crowns} args={[undefined, undefined, items.length]}>
        <icosahedronGeometry args={[1, 1]} />
        <meshLambertMaterial color="#ffffff" flatShading />
      </instancedMesh>
    </group>
  );
}

function Shrubs({ items, origin }: { items: Placement[]; origin: Origin }) {
  const mesh = useRef<THREE.InstancedMesh>(null);

  useLayoutEffect(() => {
    if (!mesh.current) return;
    const matrix = new THREE.Matrix4();
    const rotation = new THREE.Quaternion();
    const position = new THREE.Vector3();
    const scale = new THREE.Vector3();
    const color = new THREE.Color();
    items.forEach((shrub, index) => {
      const size = 0.55 + hash(shrub.id, 5) * 0.3;
      position.set(shrub.x - origin.x, size * 0.55, -(shrub.y - origin.y));
      scale.set(size, size * 0.8, size);
      mesh.current!.setMatrixAt(index, matrix.compose(position, rotation, scale));
      color.setHSL(0.22 + hash(shrub.id, 6) * 0.05, 0.4, 0.38 + hash(shrub.id, 7) * 0.08);
      mesh.current!.setColorAt(index, color);
    });
    mesh.current.instanceMatrix.needsUpdate = true;
    if (mesh.current.instanceColor) mesh.current.instanceColor.needsUpdate = true;
  }, [items, origin]);

  if (items.length === 0) return null;
  return (
    <instancedMesh key={`s${items.length}`} ref={mesh} args={[undefined, undefined, items.length]}>
      <icosahedronGeometry args={[1, 0]} />
      <meshLambertMaterial color="#ffffff" flatShading />
    </instancedMesh>
  );
}

function Buildings({ features, origin }: { features: Feature[]; origin: Origin }) {
  const geometry = useMemo(() => {
    const shapes: THREE.Shape[] = [];
    for (const feature of features) {
      if (feature.kind !== "BUILDING") continue;
      for (const polygon of polygons(feature.geometry)) {
        const [outer, ...holes] = polygon;
        if (!outer || outer.length < 4) continue;
        const shape = new THREE.Shape(outer.map(([x, y]) => new THREE.Vector2(x - origin.x, y - origin.y)));
        for (const hole of holes) {
          shape.holes.push(new THREE.Path(hole.map(([x, y]) => new THREE.Vector2(x - origin.x, y - origin.y))));
        }
        shapes.push(shape);
      }
    }
    if (shapes.length === 0) return null;
    return new THREE.ExtrudeGeometry(shapes, { depth: BUILDING_HEIGHT_M, bevelEnabled: false });
  }, [features, origin]);

  if (!geometry) return null;
  return (
    <mesh geometry={geometry} rotation={[-Math.PI / 2, 0, 0]}>
      <meshLambertMaterial color="#d8d3c8" />
    </mesh>
  );
}

function Lines({ features, site, origin }: { features: Feature[]; site: Geometry | null; origin: Origin }) {
  const groups = useMemo(() => {
    const buckets = new Map<string, number[]>();
    const push = (group: string, geometry: Geometry | null, lift: number) => {
      const target = buckets.get(group) ?? [];
      for (const line of lines(geometry)) {
        for (let i = 1; i < line.length; i++) {
          const [x0, y0] = line[i - 1];
          const [x1, y1] = line[i];
          target.push(x0 - origin.x, lift, -(y0 - origin.y), x1 - origin.x, lift, -(y1 - origin.y));
        }
      }
      buckets.set(group, target);
    };
    for (const feature of features) push(KIND_GROUP[feature.kind] ?? "other", feature.geometry, 0.04);
    push("site", site, 0.08);
    return [...buckets.entries()]
      .filter(([, values]) => values.length > 0)
      .map(([group, values]) => {
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute("position", new THREE.Float32BufferAttribute(values, 3));
        return { group, geometry };
      });
  }, [features, site, origin]);

  return (
    <group>
      {groups.map(({ group, geometry }) => (
        <lineSegments key={group} geometry={geometry}>
          <lineBasicMaterial color={group === "site" ? "#1f6b45" : LINE_COLORS[group] ?? "#888"} />
        </lineSegments>
      ))}
    </group>
  );
}

const HEDGE_WIDTH_M = 0.8;
const HEDGE_HEIGHT_M = 1.1;
const BED_HEIGHT_M = 0.25;

function Lawns({ lawn, origin }: { lawn: Geometry | null; origin: Origin }) {
  const geometry = useMemo(() => {
    const shapes: THREE.Shape[] = [];
    for (const polygon of polygons(lawn)) {
      const [outer, ...holes] = polygon;
      if (!outer || outer.length < 4) continue;
      const shape = new THREE.Shape(outer.map(([x, y]) => new THREE.Vector2(x - origin.x, y - origin.y)));
      for (const hole of holes) {
        shape.holes.push(new THREE.Path(hole.map(([x, y]) => new THREE.Vector2(x - origin.x, y - origin.y))));
      }
      shapes.push(shape);
    }
    return shapes.length ? new THREE.ShapeGeometry(shapes) : null;
  }, [lawn, origin]);

  if (!geometry) return null;
  return (
    <mesh geometry={geometry} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}>
      <meshLambertMaterial color="#9cbf73" />
    </mesh>
  );
}

function Hedges({ greening, origin }: { greening: Greening; origin: Origin }) {
  const mesh = useRef<THREE.InstancedMesh>(null);
  const segments = useMemo(() => {
    const result: { x: number; z: number; length: number; angle: number }[] = [];
    for (const hedge of greening.hedges) {
      for (let i = 1; i < hedge.coordinates.length; i++) {
        const [x0, y0] = hedge.coordinates[i - 1];
        const [x1, y1] = hedge.coordinates[i];
        const length = Math.hypot(x1 - x0, y1 - y0);
        if (length < 0.05) continue;
        result.push({
          x: (x0 + x1) / 2 - origin.x,
          z: -((y0 + y1) / 2 - origin.y),
          length,
          angle: Math.atan2(y1 - y0, x1 - x0),
        });
      }
    }
    return result;
  }, [greening, origin]);

  useLayoutEffect(() => {
    if (!mesh.current) return;
    const matrix = new THREE.Matrix4();
    const rotation = new THREE.Quaternion();
    const position = new THREE.Vector3();
    const scale = new THREE.Vector3();
    const axis = new THREE.Vector3(0, 1, 0);
    segments.forEach((segment, index) => {
      position.set(segment.x, HEDGE_HEIGHT_M / 2, segment.z);
      rotation.setFromAxisAngle(axis, segment.angle);
      scale.set(segment.length + HEDGE_WIDTH_M * 0.5, HEDGE_HEIGHT_M, HEDGE_WIDTH_M);
      mesh.current!.setMatrixAt(index, matrix.compose(position, rotation, scale));
    });
    mesh.current.instanceMatrix.needsUpdate = true;
  }, [segments]);

  if (segments.length === 0) return null;
  return (
    <instancedMesh key={`h${segments.length}`} ref={mesh} args={[undefined, undefined, segments.length]}>
      <boxGeometry args={[1, 1, 1]} />
      <meshLambertMaterial color="#3f6b35" />
    </instancedMesh>
  );
}

function Flowerbeds({ greening, origin }: { greening: Greening; origin: Origin }) {
  const mesh = useRef<THREE.InstancedMesh>(null);
  const beds = greening.flowerbeds;

  useLayoutEffect(() => {
    if (!mesh.current) return;
    const matrix = new THREE.Matrix4();
    const rotation = new THREE.Quaternion();
    const position = new THREE.Vector3();
    const scale = new THREE.Vector3();
    beds.forEach((bed, index) => {
      position.set(bed.x - origin.x, BED_HEIGHT_M / 2, -(bed.y - origin.y));
      scale.set(bed.radius_m, BED_HEIGHT_M, bed.radius_m);
      mesh.current!.setMatrixAt(index, matrix.compose(position, rotation, scale));
    });
    mesh.current.instanceMatrix.needsUpdate = true;
  }, [beds, origin]);

  if (beds.length === 0) return null;
  return (
    <instancedMesh key={`b${beds.length}`} ref={mesh} args={[undefined, undefined, beds.length]}>
      <cylinderGeometry args={[1, 1, 1, 24]} />
      <meshLambertMaterial color="#c9577a" />
    </instancedMesh>
  );
}

export default function Scene3D({ features, site, placements, greening }: Props) {
  const bounds = useMemo(
    () => boundsOf([site]) ?? boundsOf(features.map((f) => f.geometry), placements) ?? { minX: 0, minY: 0, maxX: 100, maxY: 100 },
    [site, features, placements],
  );
  const origin = useMemo(
    () => ({ x: (bounds.minX + bounds.maxX) / 2, y: (bounds.minY + bounds.maxY) / 2 }),
    [bounds],
  );
  const size = Math.max(bounds.maxX - bounds.minX, bounds.maxY - bounds.minY, 20);
  const trees = useMemo(() => placements.filter((p) => p.species_type === "tree"), [placements]);
  const shrubs = useMemo(() => placements.filter((p) => p.species_type === "shrub"), [placements]);
  const background = useMemo(() => cssColor("--map-bg", "#f4f3ee"), []);
  const ground = useMemo(() => cssColor("--map-ground", "#e6e8df"), []);
  const camera = Math.min(size * 0.55, 400);

  return (
    <div className="scene-3d">
      <Canvas camera={{ position: [camera * 0.7, camera * 0.55, camera * 0.8], fov: 40, near: 0.5, far: size * 12 }} dpr={[1, 2]}>
        <color attach="background" args={[background]} />
        <hemisphereLight args={["#ffffff", "#9aa58f", 1.4]} />
        <directionalLight position={[size * 0.4, size * 0.8, size * 0.3]} intensity={1.6} />
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.02, 0]}>
          <planeGeometry args={[size * 1.6, size * 1.6]} />
          <meshLambertMaterial color={ground} />
        </mesh>
        <Lines features={features} site={site} origin={origin} />
        <Lawns lawn={greening?.lawn ?? null} origin={origin} />
        <Buildings features={features} origin={origin} />
        {greening && <Hedges greening={greening} origin={origin} />}
        {greening && <Flowerbeds greening={greening} origin={origin} />}
        <Trees items={trees} origin={origin} />
        <Shrubs items={shrubs} origin={origin} />
        <OrbitControls makeDefault maxPolarAngle={Math.PI / 2 - 0.05} minDistance={5} maxDistance={size * 3} />
      </Canvas>
      <p className="scene-note">Высота зданий условная — {BUILDING_HEIGHT_M} м, кроны деревьев 3–5 м. Вращение — левая кнопка, сдвиг — правая, масштаб — колесо.</p>
    </div>
  );
}
