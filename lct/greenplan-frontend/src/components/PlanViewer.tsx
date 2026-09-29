import {
  Layers3,
  X,
} from "lucide-react";

import {
  useMemo,
  useState,
} from "react";

import type {
  JobResult,
  Placement,
} from "../services/api";

import type {
  PlantingType,
} from "../types/api";

type XY = {
  x: number;
  y: number;
};

const colors: Record<
  PlantingType,
  string
> = {
  tree: "#18794e",
  shrub: "#5b8c36",
  groundcover: "#9b7b25",
};

const labels: Record<
  PlantingType,
  string
> = {
  tree: "Деревья",
  shrub: "Кустарники",
  groundcover: "Покрытия",
};

const icons: Record<
  PlantingType,
  string
> = {
  tree: "🌳",
  shrub: "🌿",
  groundcover: "🍀",
};

const featureStroke: Record<
  string,
  string
> = {
  building: "#8b5e3c",
  road: "#94a3b8",
  water_pipe: "#2878a8",
  gas_pipe: "#c28b20",
  cable: "#64748b",
  powerline: "#7c3aed",
  site_boundary: "#53635b",
  unknown: "#64748b",
};

function addCoordinate(
  points: XY[],
  coordinate: unknown,
) {
  if (
    !Array.isArray(coordinate) ||
    coordinate.length < 2
  ) {
    return;
  }

  const x = coordinate[0];
  const y = coordinate[1];

  if (
    typeof x !== "number" ||
    typeof y !== "number"
  ) {
    return;
  }

  points.push({
    x,
    y,
  });
}

function getGeometryPoints(
  result: JobResult,
): XY[] {
  const points: XY[] = [];

  for (const feature of result.features) {
    const geometry = feature.geometry;

    if (!geometry) {
      continue;
    }

    if (
      geometry.type === "Point"
    ) {
      addCoordinate(
        points,
        geometry.coordinates,
      );

      continue;
    }

    if (
      geometry.type === "LineString"
    ) {
      for (const coordinate of
        geometry.coordinates) {
        addCoordinate(
          points,
          coordinate,
        );
      }

      continue;
    }

    if (
      geometry.type === "Polygon"
    ) {
      for (const ring of
        geometry.coordinates) {
        for (const coordinate of ring) {
          addCoordinate(
            points,
            coordinate,
          );
        }
      }
    }
  }

  for (const placement of result.placements) {
    points.push({
      x: placement.x,
      y: placement.y,
    });
  }

  for (const rejection of result.rejections) {
    points.push({
      x: rejection.x,
      y: rejection.y,
    });
  }

  return points;
}

export default function PlanViewer({
  result,
  selected,
  onSelect,
}: {
  result: JobResult;
  selected: Placement | null;
  onSelect: (
    placement: Placement | null,
  ) => void;
}) {
  const [filter, setFilter] =
    useState<
      "all" | PlantingType
    >("all");

  const [showConstraints, setShowConstraints] =
    useState(false);

  const width = 800;
  const height = 520;
  const padding = 35;

  const bounds = useMemo(() => {
    const points =
      getGeometryPoints(result);

    if (points.length === 0) {
      return {
        minX: 0,
        minY: 0,
        maxX: 100,
        maxY: 100,
      };
    }

    return {
      minX: Math.min(
        ...points.map(
          (item) => item.x,
        ),
      ),
      minY: Math.min(
        ...points.map(
          (item) => item.y,
        ),
      ),
      maxX: Math.max(
        ...points.map(
          (item) => item.x,
        ),
      ),
      maxY: Math.max(
        ...points.map(
          (item) => item.y,
        ),
      ),
    };
  }, [result]);

  const scaleX =
    (width - padding * 2) /
    Math.max(
      1,
      bounds.maxX - bounds.minX,
    );

  const scaleY =
    (height - padding * 2) /
    Math.max(
      1,
      bounds.maxY - bounds.minY,
    );

  const toSvgPoint = (
    x: number,
    y: number,
  ) => ({
    cx:
      padding +
      (x - bounds.minX) *
        scaleX,

    cy:
      height -
      padding -
      (y - bounds.minY) *
        scaleY,
  });

  const visiblePlacements =
    useMemo(() => {
      if (filter === "all") {
        return result.placements;
      }

      return result.placements.filter(
        (placement) =>
          placement.species_type ===
          filter,
      );
    }, [
      filter,
      result.placements,
    ]);

  return (
    <div className="viewer-shell">
      <div className="viewer-toolbar">
        <div>
          <span className="viewer-title">
            Готовый план участка
          </span>

          <span className="viewer-subtitle">
            Все посадки уже рассчитаны
            сервисом
          </span>
        </div>

        <button
          type="button"
          className={`toolbar-button ${
            showConstraints
              ? "active"
              : ""
          }`}
          onClick={() =>
            setShowConstraints(
              (value) => !value,
            )
          }
        >
          <Layers3 size={15} />

          {showConstraints
            ? "Скрыть зоны"
            : "Показать зоны"}
        </button>
      </div>

      <div className="map-filters">
        <button
          type="button"
          className={
            filter === "all"
              ? "active"
              : ""
          }
          onClick={() =>
            setFilter("all")
          }
        >
          Все
        </button>

        {(
          Object.keys(
            labels,
          ) as PlantingType[]
        ).map((type) => (
          <button
            type="button"
            key={type}
            className={
              filter === type
                ? "active"
                : ""
            }
            onClick={() =>
              setFilter(type)
            }
          >
            {icons[type]}{" "}
            {labels[type]}
          </button>
        ))}
      </div>

      <div className="map-stage">
        <svg
          className="plan-svg"
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label="Рассчитанный план озеленения"
        >
          <rect
            x="0"
            y="0"
            width={width}
            height={height}
            fill="#f8faf8"
          />

          {result.features.map(
            (feature) => {
              const geometry =
                feature.geometry;

              if (!geometry) {
                return null;
              }

              const stroke =
                featureStroke[
                  feature.kind
                ] ?? "#64748b";

              if (
                geometry.type ===
                "Point"
              ) {
                const coordinates =
                  geometry.coordinates;

                if (
                  coordinates.length <
                  2
                ) {
                  return null;
                }

                const x =
                  coordinates[0];

                const y =
                  coordinates[1];

                if (
                  typeof x !==
                    "number" ||
                  typeof y !==
                    "number"
                ) {
                  return null;
                }

                const q =
                  toSvgPoint(x, y);

                return (
                  <circle
                    key={feature.id}
                    cx={q.cx}
                    cy={q.cy}
                    r="4"
                    fill={stroke}
                  />
                );
              }

              if (
                geometry.type ===
                "LineString"
              ) {
                const points =
                  geometry.coordinates
                    .map(
                      (
                        coordinate,
                      ) => {
                        if (
                          coordinate.length <
                          2
                        ) {
                          return null;
                        }

                        const x =
                          coordinate[0];

                        const y =
                          coordinate[1];

                        if (
                          typeof x !==
                            "number" ||
                          typeof y !==
                            "number"
                        ) {
                          return null;
                        }

                        const q =
                          toSvgPoint(
                            x,
                            y,
                          );

                        return `${q.cx},${q.cy}`;
                      },
                    )
                    .filter(
                      (
                        value,
                      ): value is string =>
                        value !== null,
                    )
                    .join(" ");

                return (
                  <polyline
                    key={feature.id}
                    points={points}
                    fill="none"
                    stroke={stroke}
                    strokeWidth={
                      feature.kind ===
                      "road"
                        ? 12
                        : 3
                    }
                    strokeLinecap="round"
                    opacity={
                      feature.kind ===
                      "road"
                        ? 0.42
                        : 0.9
                    }
                  />
                );
              }

              if (
                geometry.type ===
                "Polygon"
              ) {
                const points =
                  geometry.coordinates[0]
                    ?.map(
                      (
                        coordinate,
                      ) => {
                        if (
                          coordinate.length <
                          2
                        ) {
                          return null;
                        }

                        const x =
                          coordinate[0];

                        const y =
                          coordinate[1];

                        if (
                          typeof x !==
                            "number" ||
                          typeof y !==
                            "number"
                        ) {
                          return null;
                        }

                        const q =
                          toSvgPoint(
                            x,
                            y,
                          );

                        return `${q.cx},${q.cy}`;
                      },
                    )
                    .filter(
                      (
                        value,
                      ): value is string =>
                        value !== null,
                    )
                    .join(" ");

                return (
                  <polygon
                    key={feature.id}
                    points={points}
                    fill={
                      feature.kind ===
                      "building"
                        ? "#e7ddd3"
                        : "none"
                    }
                    stroke={stroke}
                    strokeWidth="2"
                  />
                );
              }

              return null;
            },
          )}

          {showConstraints && (
            <>
              <line
                x1="0"
                y1="305"
                x2="800"
                y2="305"
                stroke="#d6b36a"
                strokeWidth="30"
                opacity=".14"
              />

              <line
                x1="440"
                y1="0"
                x2="440"
                y2="520"
                stroke="#d6b36a"
                strokeWidth="30"
                opacity=".14"
              />
            </>
          )}

          {result.rejections.map(
            (rejection) => {
              const q =
                toSvgPoint(
                  rejection.x,
                  rejection.y,
                );

              return (
                <g
                  key={`rejection-${rejection.id}`}
                  transform={`translate(${q.cx} ${q.cy})`}
                  opacity=".48"
                >
                  <circle
                    r="7"
                    fill="none"
                    stroke="#c2413a"
                    strokeWidth="2"
                  />

                  <line
                    x1="-5"
                    y1="-5"
                    x2="5"
                    y2="5"
                    stroke="#c2413a"
                    strokeWidth="2"
                  />

                  <line
                    x1="-5"
                    y1="5"
                    x2="5"
                    y2="-5"
                    stroke="#c2413a"
                    strokeWidth="2"
                  />
                </g>
              );
            },
          )}

          {visiblePlacements.map(
            (placement) => {
              const q =
                toSvgPoint(
                  placement.x,
                  placement.y,
                );

              const active =
                placement.id ===
                selected?.id;

              const type =
                placement.species_type;

              return (
                <g
                  key={placement.id}
                  transform={`translate(${q.cx} ${q.cy})`}
                  onClick={() =>
                    onSelect(
                      placement,
                    )
                  }
                  className="placement-point"
                  tabIndex={0}
                  role="button"
                  aria-label={`${labels[type]} №${placement.id}`}
                  onKeyDown={(
                    event,
                  ) => {
                    if (
                      event.key ===
                        "Enter" ||
                      event.key === " "
                    ) {
                      onSelect(
                        placement,
                      );
                    }
                  }}
                >
                  <circle
                    r={
                      active ? 11 : 8
                    }
                    fill="white"
                    stroke={
                      colors[type]
                    }
                    strokeWidth={
                      active ? 4 : 3
                    }
                  />

                  <circle
                    r={
                      active ? 5 : 4
                    }
                    fill={
                      colors[type]
                    }
                  />
                </g>
              );
            },
          )}
        </svg>

        {selected && (
          <button
            type="button"
            className="map-selection"
            onClick={() =>
              onSelect(null)
            }
            aria-label="Закрыть информацию о посадке"
          >
            <span>
              {
                icons[
                  selected.species_type
                ]
              }{" "}
              Посадка №
              {selected.id}
            </span>

            <X size={15} />
          </button>
        )}
      </div>

      <div className="legend">
        {(
          Object.keys(
            labels,
          ) as PlantingType[]
        ).map((type) => (
          <span key={type}>
            <i
              style={{
                background:
                  colors[type],
              }}
            />

            {labels[type]}
          </span>
        ))}

        <span>
          <i className="legend-line water" />
          Коммуникации
        </span>

        <span>
          <i className="legend-cross" />
          Отклонённый кандидат
        </span>
      </div>
    </div>
  );
}
