import { useMemo } from "react";
import "./ThreeDViewer.css";
import { Canvas } from "@react-three/fiber";
import { Grid, Line, OrbitControls } from "@react-three/drei";
import type { Feature, JobResult, Placement } from "../services/api";
import type { ThreeEvent } from "@react-three/fiber";

 type Point2 = { x: number; y: number };
 type Point3 = [number, number, number];

const PLANT_COLORS = {
  tree: "#347b43",
  shrub: "#79a84a",
  groundcover: "#a6bd58",
};

function collectCoordinatePairs(value: unknown, output: Point2[]) {
  if (!Array.isArray(value)) return;
  if (
    value.length >= 2 &&
    typeof value[0] === "number" &&
    typeof value[1] === "number"
  ) {
    output.push({ x: value[0], y: value[1] });
    return;
  }
  for (const item of value) collectCoordinatePairs(item, output);
}

function featurePoints(feature: Feature): Point2[] {
  const output: Point2[] = [];
  const geometry = feature.geometry as unknown as { coordinates?: unknown } | undefined;
  if (geometry?.coordinates !== undefined) {
    collectCoordinatePairs(geometry.coordinates, output);
  }
  return output;
}

function mapPoint(point: Point2, bounds: { minX: number; minY: number; size: number }): Point3 {
  const scale = 60 / bounds.size;
  return [
    (point.x - bounds.minX) * scale - 30,
    0,
    (point.y - bounds.minY) * scale - 30,
  ];
}

function Plant({ placement, position }: { placement: Placement; position: Point3 }) {
  const color = PLANT_COLORS[placement.species_type] ?? PLANT_COLORS.tree;
  const isTree = placement.species_type === "tree";
  const isShrub = placement.species_type === "shrub";
  const radius = isTree ? 0.85 : isShrub ? 0.55 : 0.7;

  const handleClick = (event: ThreeEvent<MouseEvent>) => {
    event.stopPropagation();
  };

  return (
    <group position={position} onClick={handleClick}>
      {isTree ? (
        <>
          <mesh position={[0, 1.15, 0]} castShadow>
            <cylinderGeometry args={[0.12, 0.18, 2.3, 8]} />
            <meshStandardMaterial color="#866044" />
          </mesh>
          <mesh position={[0, 2.65, 0]} castShadow>
            <sphereGeometry args={[radius, 12, 10]} />
            <meshStandardMaterial color={color} roughness={0.9} />
          </mesh>
        </>
      ) : isShrub ? (
        <mesh position={[0, 0.45, 0]} castShadow>
          <sphereGeometry args={[radius, 10, 8]} />
          <meshStandardMaterial color={color} roughness={1} />
        </mesh>
      ) : (
        <mesh position={[0, 0.08, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
          <circleGeometry args={[radius, 16]} />
          <meshStandardMaterial color={color} roughness={1} />
        </mesh>
      )}
    </group>
  );
}

function FeatureLines({ features, bounds }: { features: Feature[]; bounds: { minX: number; minY: number; size: number } }) {
  return (
    <group>
      {features.map((feature) => {
        const points = featurePoints(feature);
        if (points.length < 2) return null;
        const linePoints = points.map((point) => mapPoint(point, bounds));
        const color = feature.kind === "building"
          ? "#9b7b67"
          : feature.kind === "road"
            ? "#a7afb7"
            : feature.kind === "site_boundary"
              ? "#64786a"
              : feature.kind === "water_pipe"
                ? "#3c8fc0"
                : feature.kind === "gas_pipe"
                  ? "#c99b36"
                  : "#7c83a3";
        return (
          <Line
            key={feature.id}
            points={linePoints}
            color={color}
            lineWidth={feature.kind === "site_boundary" ? 2 : 1}
            dashed={feature.kind !== "building" && feature.kind !== "road" && feature.kind !== "site_boundary"}
          />
        );
      })}
    </group>
  );
}

export default function ThreeDViewer({ result }: { result: JobResult }) {
  const { bounds, plantPositions } = useMemo(() => {
    // В 3D показываем только посадки, прошедшие проверку норм.
    // Статусы "rejected" и "warning" не считаем подтверждёнными посадками.
    const displayedPlacements = result.placements.filter(
      (placement) => placement.status === "allowed",
    );
    const allPoints: Point2[] = [];
    for (const feature of result.features) allPoints.push(...featurePoints(feature));
    for (const placement of displayedPlacements) allPoints.push({ x: placement.x, y: placement.y });

    if (allPoints.length === 0) allPoints.push({ x: 0, y: 0 }, { x: 100, y: 100 });
    const minX = Math.min(...allPoints.map((point) => point.x));
    const maxX = Math.max(...allPoints.map((point) => point.x));
    const minY = Math.min(...allPoints.map((point) => point.y));
    const maxY = Math.max(...allPoints.map((point) => point.y));
    const size = Math.max(maxX - minX, maxY - minY, 1);
    const nextBounds = { minX, minY, size };
    return {
      bounds: nextBounds,
      plantPositions: displayedPlacements.map((placement) => ({
        placement,
        position: mapPoint({ x: placement.x, y: placement.y }, nextBounds),
      })),
    };
  }, [result.features, result.placements]);

  return (
    <section className="greenplan-3d-panel" aria-label="Трёхмерный просмотр плана">
      <div className="greenplan-3d-canvas">
        <Canvas camera={{ position: [48, 42, 55], fov: 45 }} shadows>
          <color attach="background" args={["#f4f7f3"]} />
          <ambientLight intensity={1.2} />
          <directionalLight position={[25, 45, 20]} intensity={2} castShadow />
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.06, 0]} receiveShadow>
            <planeGeometry args={[80, 80]} />
            <meshStandardMaterial color="#e8ede5" />
          </mesh>
          <Grid
            position={[0, -0.045, 0]}
            args={[80, 80]}
            cellSize={2}
            cellThickness={0.45}
            cellColor="#b8c5b5"
            sectionSize={10}
            sectionThickness={0.8}
            sectionColor="#8fa18b"
            fadeDistance={100}
            infiniteGrid={false}
          />
          <FeatureLines features={result.features} bounds={bounds} />
          {plantPositions.map(({ placement, position }) => (
            <Plant key={placement.id} placement={placement} position={position} />
          ))}
          <OrbitControls makeDefault minDistance={12} maxDistance={110} maxPolarAngle={Math.PI / 2 - 0.03} />
        </Canvas>
      </div>
      <div className="greenplan-3d-footer">
        <span>Перетаскивайте мышью, чтобы вращать сцену; колёсико — масштаб.</span>
      </div>
    </section>
  );
}
