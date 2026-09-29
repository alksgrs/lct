import {
  CheckCircle2,
  Leaf,
  Trees
} from "lucide-react";

import type { JobResult } from "../types/api";

export default function SummaryCards({
  summary
}: {
  summary: JobResult["summary"];
}) {
  const normsPassed =
    summary.normsPassed ?? true;

  const groundcoverArea =
    summary.groundcoversAreaM2 ??
    summary.groundcovers * 40;

  return (
    <div className="summary-grid">
      <div className="stat-card">
        <div className="stat-icon tree">
          <Trees size={21} />
        </div>

        <span>Деревья</span>

        <strong>
          {summary.trees} шт.
        </strong>
      </div>

      <div className="stat-card">
        <div className="stat-icon shrub">
          <Leaf size={21} />
        </div>

        <span>Кустарники</span>

        <strong>
          {summary.shrubs} шт.
        </strong>
      </div>

      <div className="stat-card">
        <div className="stat-icon ground">
          <Leaf size={21} />
        </div>

        <span>Покрытия</span>

        <strong>
          {groundcoverArea} м²
        </strong>
      </div>

      <div
        className={`stat-card norm-card ${
          normsPassed
            ? "passed"
            : "failed"
        }`}
      >
        <div className="stat-icon">
          <CheckCircle2 size={21} />
        </div>

        <span>
          Проверка норм
        </span>

        <strong>
          {normsPassed
            ? "Нарушений не обнаружено"
            : "Требуется проверка"}
        </strong>
      </div>
    </div>
  );
}