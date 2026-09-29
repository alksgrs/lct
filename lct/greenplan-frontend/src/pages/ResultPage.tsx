import {
  Download,
  FileText,
  RotateCcw
} from "lucide-react";

import { useState } from "react";

import Layout from "../components/Layout";
import PlanViewer from "../components/PlanViewer";
import PlacementDetails from "../components/PlacementDetails";
import RejectionList from "../components/RejectionList";
import SummaryCards from "../components/SummaryCards";

import {
  downloadDxf,
  downloadInterpretation
} from "../services/api";

import type {
  JobResult,
  Placement
} from "../types/api";

export default function ResultPage({
  result,
  onRestart
}: {
  result: JobResult;
  onRestart: () => void;
}) {
  const [selected, setSelected] =
    useState<Placement | null>(null);

  const [showRejections, setShowRejections] =
    useState(false);

  const [downloading, setDownloading] =
    useState<
      "dxf" | "report" | null
    >(null);

  const handleDownload = async (
    type: "dxf" | "report"
  ) => {
    setDownloading(type);

    try {
      if (type === "dxf") {
        await downloadDxf(
          result.job.id,
          result
        );
      } else {
        await downloadInterpretation(
          result.job.id,
          result
        );
      }
    } finally {
      setDownloading(null);
    }
  };

  return (
    <Layout>
      <section className="result-intro">
        <div>
          <span className="eyebrow">
            Расчёт завершён
          </span>

          <h1>
            Готовый план озеленения
          </h1>

          <p>
            {result.job.inputFile}
            {" · "}
            все посадки рассчитаны
            автоматически
          </p>
        </div>

        <button
          className="secondary-button"
          type="button"
          onClick={onRestart}
        >
          <RotateCcw size={16} />
          Новый расчёт
        </button>
      </section>

      <div className="result-layout">
        <section className="panel viewer-panel">
          <PlanViewer
            result={result}
            selected={selected}
            onSelect={setSelected}
          />
        </section>

        <aside className="result-sidebar">
          <SummaryCards
            summary={result.summary}
          />

          <div className="download-card">
            <span className="download-eyebrow">
              Готовые материалы
            </span>

            <h2>
              Скачать результат
            </h2>

            <p>
              Сохраните рассчитанный план
              и поясняющий отчёт.
            </p>

            <button
              className="primary-button full-width"
              type="button"
              onClick={() =>
                void handleDownload("dxf")
              }
              disabled={
                downloading !== null
              }
            >
              <Download size={17} />

              {downloading === "dxf"
                ? "Подготовка…"
                : "Скачать DXF"}
            </button>

            <button
              className="secondary-button full-width"
              type="button"
              onClick={() =>
                void handleDownload(
                  "report"
                )
              }
              disabled={
                downloading !== null
              }
            >
              <FileText size={17} />

              {downloading === "report"
                ? "Подготовка…"
                : "Скачать отчёт"}
            </button>
          </div>
        </aside>
      </div>

      <section className="result-note">
        <div>
          <strong>
            Нажмите на посадку на карте
          </strong>

          <span>
            Откроется её нормативное
            обоснование и проверенные
            отступы.
          </span>
        </div>

        {result.rejections.length >
          0 && (
          <button
            type="button"
            className="secondary-button"
            onClick={() =>
              setShowRejections(
                (value) => !value
              )
            }
          >
            {showRejections
              ? "Скрыть отклонения"
              : `Показать отклонённые кандидаты (${result.rejections.length})`}
          </button>
        )}
      </section>

      {showRejections && (
        <section className="panel rejection-panel">
          <div className="panel-heading compact">
            <div>
              <h2>
                Отклонённые кандидаты
              </h2>

              <p>
                Сервис сохраняет объяснение,
                почему точка не была включена
                в готовый план.
              </p>
            </div>
          </div>

          <RejectionList
            items={result.rejections}
          />
        </section>
      )}

      {selected && (
        <PlacementDetails
          placement={selected}
          onClose={() =>
            setSelected(null)
          }
        />
      )}
    </Layout>
  );
}