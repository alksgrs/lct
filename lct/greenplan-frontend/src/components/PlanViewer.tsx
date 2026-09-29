import {
  Layers3,
  X
} from "lucide-react";

import {
  useMemo,
  useState
} from "react";

import type {
  JobResult,
  Placement,
  PlantingType
} from "../types/api";

const colors: Record<
  PlantingType,
  string
> = {
  tree: "#18794e",
  shrub: "#5b8c36",
  groundcover: "#9b7b25"
};

const labels: Record<
  PlantingType,
  string
> = {
  tree: "Деревья",
  shrub: "Кустарники",
  groundcover: "Покрытия"
};

const icons: Record<
  PlantingType,
  string
> = {
  tree: "🌳",
  shrub: "🌿",
  groundcover: "🍀"
};

export default function PlanViewer({
  result,
  selected,
  onSelect
}: {
  result: JobResult;
  selected: Placement | null;
  onSelect: (
    placement: Placement | null
  ) => void;
}) {
  const [filter, setFilter] =
    useState<
      "all" | PlantingType
    >("all");

  const [showConstraints, setShowConstraints] =
    useState(false);

  const { bounds } = result;

  const width = 800;
  const height = 520;

  const sx =
    width /
    Math.max(
      1,
      bounds.maxX - bounds.minX
    );

  const sy =
    height /
    Math.max(
      1,
      bounds.maxY - bounds.minY
    );

  const point = (
    x: number,
    y: number
  ) => ({
    cx:
      (x - bounds.minX) *
      sx,

    cy:
      height -
      (y - bounds.minY) *
        sy
  });

  const featureStroke: Record<
    string,
    string
  > = {
    site: "#53635b",
    building: "#8b5e3c",
    water: "#2878a8",
    gas: "#c28b20",
    road: "#94a3b8"
  };

  const visiblePlacements =
    useMemo(
      () =>
        filter === "all"
          ? result.placements
          : result.placements.filter(
              (placement) =>
                placement.species_type ===
                filter
            ),
      [filter, result.placements]
    );

  const selectedId =
    selected?.id;

  return (
    <div className="viewer-shell">
      <div className="viewer-toolbar">
        <div>
          <span className="viewer-title">
            Готовый план участка
          </span>

          <span className="viewer-subtitle">
            Все посадки уже рассчитаны сервисом
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
              (value) => !value
            )
          }
        >
          <Layers3 size={15} />

          {showConstraints
            ? "Скрыть зоны"
            : "Показать зоны"}
        </button>
      </div>

      <div
        className="map-filters"
        aria-label="Фильтр отображения посадок"
      >
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
            labels
          ) as PlantingType[]
        ).map((type) => (
          <button
            type="button"
            className={
              filter === type
                ? "active"
                : ""
            }
            onClick={() =>
              setFilter(type)
            }
            key={type}
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

          {result.features
            .filter(
              (feature) =>
                feature.type !== "site"
            )
            .map((feature) => {
              const points =
                feature.points
                  .map((p) => {
                    const q =
                      point(
                        p.x,
                        p.y
                      );

                    return `${q.cx},${q.cy}`;
                  })
                  .join(" ");

              return feature.type ===
                "building" ? (
                <polygon
                  key={feature.id}
                  points={points}
                  fill="#e7ddd3"
                  stroke={
                    featureStroke.building
                  }
                  strokeWidth="2"
                />
              ) : (
                <polyline
                  key={feature.id}
                  points={points}
                  fill="none"
                  stroke={
                    featureStroke[
                      feature.type
                    ] ?? "#64748b"
                  }
                  strokeWidth={
                    feature.type === "road"
                      ? 12
                      : 3
                  }
                  strokeLinecap="round"
                  opacity={
                    feature.type === "road"
                      ? 0.42
                      : 0.95
                  }
                />
              );
            })}

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
                point(
                  rejection.x,
                  rejection.y
                );

              return (
                <g
                  key={`r-${rejection.id}`}
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
            }
          )}

          {visiblePlacements.map(
            (placement) => {
              const q =
                point(
                  placement.x,
                  placement.y
                );

              const active =
                placement.id ===
                selectedId;

              const isGroundcover =
                placement.species_type ===
                "groundcover";

              return (
                <g
                  key={placement.id}
                  transform={`translate(${q.cx} ${q.cy})`}
                  onClick={() =>
                    onSelect(placement)
                  }
                  className="placement-point"
                  tabIndex={0}
                  role="button"
                  aria-label={`${labels[placement.species_type]} №${placement.id}`}
                  onKeyDown={(
                    event
                  ) => {
                    if (
                      event.key ===
                        "Enter" ||
                      event.key ===
                        " "
                    ) {
                      onSelect(
                        placement
                      );
                    }
                  }}
                >
                  <circle
                    r={
                      active
                        ? 11
                        : 8
                    }
                    fill="white"
                    stroke={
                      colors[
                        placement
                          .species_type
                      ]
                    }
                    strokeWidth={
                      active
                        ? 4
                        : 3
                    }
                  />

                  {isGroundcover ? (
                    <rect
                      x={
                        active
                          ? -4
                          : -3
                      }
                      y={
                        active
                          ? -4
                          : -3
                      }
                      width={
                        active
                          ? 8
                          : 6
                      }
                      height={
                        active
                          ? 8
                          : 6
                      }
                      rx="2"
                      fill={
                        colors[
                          placement
                            .species_type
                        ]
                      }
                    />
                  ) : (
                    <circle
                      r={
                        active
                          ? 5
                          : 4
                      }
                      fill={
                        colors[
                          placement
                            .species_type
                        ]
                      }
                    />
                  )}
                </g>
              );
            }
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
            labels
          ) as PlantingType[]
        ).map((type) => (
          <span key={type}>
            <i
              style={{
                background:
                  colors[type]
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