import {
  Download,
  FileText,
  RotateCcw,
} from "lucide-react";

import { useState } from "react";

import Layout from "../components/Layout";
import PlanViewer from "../components/PlanViewer";
import PlacementDetails from "../components/PlacementDetails";
import RejectionList from "../components/RejectionList";

import {
  downloadDxf,
} from "../services/api";

import type {
  JobResult,
  Placement,
} from "../services/api";

import type {
  PlantingType,
} from "../types/api";

export default function ResultPage({
  result,
  onRestart,
}: {
  result: JobResult;
  onRestart: () => void;
}) {
  const [selected, setSelected] =
    useState<Placement | null>(null);

  const [activeType, setActiveType] =
    useState<PlantingType | null>(null);

  const [showRejections, setShowRejections] =
    useState(false);

  const [downloading, setDownloading] =
    useState<"dxf" | "report" | null>(null);

  const visiblePlacements =
    activeType
      ? result.placements.filter(
          (placement) =>
            placement.species_type ===
            activeType,
        )
      : result.placements;

  const handleShowType = (
    type: PlantingType,
  ) => {
    setActiveType((current) =>
      current === type ? null : type,
    );
  };

  const handleDownloadDxf = async () => {
    setDownloading("dxf");

    try {
      await downloadDxf(result.run_id);
    } finally {
      setDownloading(null);
    }
  };

  const handleDownloadReport = () => {
    setDownloading("report");

    try {
      const report = {
        run_id: result.run_id,
        status: result.status,
        statistics: result.statistics,
        placements: result.placements,
        rejections: result.rejections,
      };

      const blob = new Blob(
        [JSON.stringify(report, null, 2)],
        {
          type: "application/json;charset=utf-8",
        },
      );

      const url =
        URL.createObjectURL(blob);

      const link =
        document.createElement("a");

      link.href = url;
      link.download =
        "greenplan-report.json";

      document.body.appendChild(link);
      link.click();
      link.remove();

      URL.revokeObjectURL(url);
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
            Все посадки рассчитаны
            автоматически.
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
        <main className="result-main">
          <section className="panel viewer-panel">
            <div className="map-card-header">
              <div>
                <div className="map-card-title">
                  План участка
                </div>

                <div className="map-card-subtitle">
                  {activeType
                    ? `Фильтр: ${
                        activeType === "tree"
                          ? "деревья"
                          : activeType === "shrub"
                            ? "кустарники"
                            : "почвопокровные"
                      }`
                    : "Все размещения"}
                </div>
              </div>

              {activeType && (
                <button
                  type="button"
                  className="clear-map-filter"
                  onClick={() =>
                    setActiveType(null)
                  }
                >
                  Сбросить фильтр
                </button>
              )}
            </div>

            <PlanViewer
              result={result}
              selected={selected}
              onSelect={setSelected}
            />
          </section>

          {selected && (
            <PlacementDetails
              placement={selected}
              onClose={() =>
                setSelected(null)
              }
            />
          )}

          <section className="panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">
                  ПРОВЕРКА НОРМ
                </span>

                <h2>
                  Отклонённые размещения
                </h2>

                <p>
                  Количество отклонённых
                  кандидатов:{" "}
                  {result.rejections.length}
                </p>
              </div>
            </div>

            {result.rejections.length ===
            0 ? (
              <div className="rejections-empty">
                <span className="rejections-empty-icon">
                  ✓
                </span>

                <div>
                  <strong>
                    Нарушений не обнаружено
                  </strong>

                  <p>
                    Все рассчитанные точки
                    прошли проверку
                    ограничений.
                  </p>
                </div>
              </div>
            ) : (
              <RejectionList
                items={result.rejections}
              />
            )}
          </section>
        </main>

        <aside className="result-sidebar">
          <section className="panel">
            <span className="eyebrow">
              РЕЗУЛЬТАТ
            </span>

            <h2>
              План озеленения готов
            </h2>

            <div className="result-cards">
              <button
                type="button"
                className="result-card tree-card"
                onClick={() =>
                  handleShowType("tree")
                }
              >
                <span className="result-card-icon">
                  🌳
                </span>

                <strong>
                  {result.statistics.trees}
                </strong>

                <span>
                  Деревья
                </span>
              </button>

              <button
                type="button"
                className="result-card shrub-card"
                onClick={() =>
                  handleShowType("shrub")
                }
              >
                <span className="result-card-icon">
                  🌿
                </span>

                <strong>
                  {result.statistics.shrubs}
                </strong>

                <span>
                  Кустарники
                </span>
              </button>

              <button
                type="button"
                className="result-card groundcover-card"
                onClick={() =>
                  handleShowType(
                    "groundcover",
                  )
                }
              >
                <span className="result-card-icon">
                  🍀
                </span>

                <strong>
                  {
                    result.statistics
                      .groundcovers_area_m2
                  }{" "}
                  м²
                </strong>

                <span>
                  Покрытия
                </span>
              </button>
            </div>

            <div className="result-status">
              ✓ Проверка норм — Нарушений
              не обнаружено
            </div>
          </section>

          <section className="panel download-card">
            <span className="eyebrow">
              ГОТОВЫЕ МАТЕРИАЛЫ
            </span>

            <h2>
              Скачать результат
            </h2>

            <p>
              Сохраните рассчитанный план
              и отчёт.
            </p>

            <button
              className="primary-button full"
              type="button"
              onClick={() =>
                void handleDownloadDxf()
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
              className="secondary-button full"
              type="button"
              onClick={
                handleDownloadReport
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
          </section>
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

        {result.rejections.length > 0 && (
          <button
            type="button"
            className="secondary-button"
            onClick={() =>
              setShowRejections(
                (value) => !value,
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
          <RejectionList
            items={result.rejections}
          />
        </section>
      )}
    </Layout>
  );
}
