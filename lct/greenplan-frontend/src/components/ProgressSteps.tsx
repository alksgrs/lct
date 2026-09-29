const stages = [
  ["parsing_dxf", "Разбор DXF"],
  ["building_constraints", "Допустимые зоны"],
  ["generating_placements", "Размещение посадок"],
  ["writing_output", "Формирование плана"],
  ["completed", "Готово"]
] as const;

export default function ProgressSteps({
  stage,
  progress
}: {
  stage?: string;
  progress?: number;
}) {
  const current =
    stages.findIndex(
      ([id]) => id === stage
    );

  const normalized =
    Math.max(
      0,
      Math.min(
        100,
        progress ?? 0
      )
    );

  return (
    <div className="progress-block">
      <div className="progress-topline">
        <span>Ход расчёта</span>
        <strong>
          {normalized}%
        </strong>
      </div>

      <div className="progress-track">
        <div
          style={{
            width: `${normalized}%`
          }}
        />
      </div>

      <div className="steps">
        {stages.map(
          ([id, label], index) => (
            <div
              className={`step ${
                index <= current
                  ? "done"
                  : ""
              } ${
                id === stage
                  ? "active"
                  : ""
              }`}
              key={id}
            >
              <span className="step-dot">
                {index < current
                  ? "✓"
                  : index + 1}
              </span>

              <span>{label}</span>
            </div>
          )
        )}
      </div>
    </div>
  );
}