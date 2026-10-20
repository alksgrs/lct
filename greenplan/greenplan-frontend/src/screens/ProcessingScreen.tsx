import LayersPanel from "../components/LayersPanel";
import type { Job } from "../types";

interface Props {
  job: Job;
  busy: boolean;
  onApplyLayers: (overrides: Record<string, string>, boundaryLayer: string | null) => void;
  onRestart: () => void;
}

const STAGES: [number, string][] = [
  [5, "Чтение DXF, распознавание слоёв"],
  [30, "Граница участка"],
  [40, "Размещение деревьев"],
  [65, "Размещение кустарников"],
  [82, "Газоны, изгороди, цветники"],
  [92, "Сбор результата"],
];

export default function ProcessingScreen({ job, busy, onApplyLayers, onRestart }: Props) {
  const failed = job.status === "failed";
  const progress = Math.max(2, Math.min(100, job.progress));

  return (
    <main className="processing">
      <header className="processing-head">
        <p className="mono muted small">{job.filename}</p>
        <h1>{failed ? "Расчёт остановлен" : "Идёт расчёт"}</h1>
      </header>

      {!failed && (
        <>
          <div className="progress" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
            <span style={{ width: `${progress}%` }} />
          </div>
          <ol className="stages">
            {STAGES.map(([threshold, label], index) => {
              const next = STAGES[index + 1]?.[0] ?? 100;
              const state = job.progress >= next ? "done" : job.progress >= threshold ? "current" : "todo";
              return (
                <li key={label} className={`stage stage-${state}`}>
                  <span className="stage-mark" />
                  {label}
                </li>
              );
            })}
          </ol>
          <p className="muted small">Крупная подоснова считается до минуты.</p>
        </>
      )}

      {failed && (
        <>
          <p className="error-box">{job.error ?? "Не удалось обработать файл."}</p>
          {job.layers && job.layers.length > 0 && job.allowed_kinds ? (
            <section className="processing-layers">
              <h2>Слои чертежа</h2>
              <LayersPanel
                layers={job.layers}
                kinds={job.allowed_kinds}
                overrides={job.overrides ?? {}}
                boundaryLayer={job.boundary_layer ?? null}
                busy={busy}
                onApply={onApplyLayers}
              />
            </section>
          ) : null}
          <button type="button" className="secondary-button" onClick={onRestart}>
            Загрузить другой файл
          </button>
        </>
      )}
    </main>
  );
}
