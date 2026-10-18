import {
  Download,
  FileText,
  Pencil,
  RotateCcw,
  Save,
  Undo2,
} from "lucide-react";

import { useMemo, useState } from "react";

import Layout from "../components/Layout";
import PlanViewer from "../components/PlanViewer";
import ThreeDViewer from "../components/ThreeDViewer";
import PlacementDetails from "../components/PlacementDetails";
import RejectionList from "../components/RejectionList";

import {
  downloadOriginalDxf,
  downloadEditedDxf,
  saveEdits,
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

  const [placements, setPlacements] =
    useState<Placement[]>(() => result.placements.map((item) => ({ ...item })));

  // The baseline advances only after the backend confirms a successful save.
  const [savedPlacements, setSavedPlacements] =
    useState<Placement[]>(() => result.placements.map((item) => ({ ...item })));
  const [hasSavedEdits, setHasSavedEdits] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  const [isEditing, setIsEditing] = useState(false);
  const [viewerMode, setViewerMode] = useState<"2d" | "3d">("2d");

  const [undoStack, setUndoStack] = useState<Placement[][]>([]);

  const hasUnsavedChanges = useMemo(
    () =>
      placements.length !== savedPlacements.length ||
      placements.some((placement, index) => {
        const saved = savedPlacements[index];
        return (
          !saved ||
          placement.id !== saved.id ||
          placement.x !== saved.x ||
          placement.y !== saved.y
        );
      }),
    [placements, savedPlacements],
  );

  const [activeType, setActiveType] =
    useState<PlantingType | null>(null);

  const [showRejections, setShowRejections] =
    useState(false);

  const [downloading, setDownloading] =
    useState<"dxf" | "edited-dxf" | "report" | null>(null);

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

  const handleDragStart = () => {
    setUndoStack((current) => [
      ...current,
      placements.map((item) => ({ ...item })),
    ].slice(-50));
  };

  const handleMovePlacement = (
    id: string,
    x: number,
    y: number,
  ) => {
    setPlacements((current) =>
      current.map((placement) =>
        placement.id === id
          ? { ...placement, x, y }
          : placement,
      ),
    );

    setSelected((current) =>
      current?.id === id
        ? { ...current, x, y }
        : current,
    );
  };

  const handleUndo = () => {
    if (undoStack.length === 0) {
      return;
    }

    const previous = undoStack[undoStack.length - 1];
    setPlacements(previous.map((item) => ({ ...item })));
    setUndoStack((current) => current.slice(0, -1));
    setSelected((current) => {
      if (!current) return null;
      return previous.find((item) => item.id === current.id) ?? null;
    });
  };

  const handleResetPlacements = () => {
    const baseline = savedPlacements.map((item) => ({ ...item }));
    setPlacements(baseline);
    setUndoStack([]);
    setSaveMessage(null);
    setSelected((current) => {
      if (!current) return null;
      return baseline.find((item) => item.id === current.id) ?? null;
    });
  };

  const handleSaveEdits = async () => {
    if (!hasUnsavedChanges || saving) return;
    setSaving(true);
    setSaveMessage(null);
    try {
      const response = await saveEdits(result.run_id, placements);
      const saved = response.result.placements.map((item) => ({ ...item }));
      setPlacements(saved);
      setSavedPlacements(saved.map((item) => ({ ...item })));
      setHasSavedEdits(true);
      setUndoStack([]);
      setSelected((current) => current ? saved.find((item) => item.id === current.id) ?? null : null);
      setSaveMessage("Изменения сохранены. Исходный DXF не изменён.");
    } catch (error) {
      setSaveMessage(error instanceof Error ? error.message : "Не удалось сохранить изменения.");
    } finally {
      setSaving(false);
    }
  };

  const handleDownloadOriginalDxf = async () => {
    setDownloading("dxf");
    try {
      await downloadOriginalDxf(result.run_id);
    } finally {
      setDownloading(null);
    }
  };

  const handleDownloadEditedDxf = async () => {
    setDownloading("edited-dxf");
    try {
      await downloadEditedDxf(result.run_id);
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

            <div className="viewer-mode-switch" role="tablist" aria-label="Режим просмотра участка">
              <button
                type="button"
                role="tab"
                aria-selected={viewerMode === "2d"}
                className={`secondary-button ${viewerMode === "2d" ? "active" : ""}`}
                onClick={() => setViewerMode("2d")}
              >
                2D-план
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={viewerMode === "3d"}
                className={`secondary-button ${viewerMode === "3d" ? "active" : ""}`}
                onClick={() => {
                  setViewerMode("3d");
                  setIsEditing(false);
                }}
              >
                3D-просмотр
              </button>
            </div>

            {viewerMode === "2d" && <div className="viewer-edit-toolbar">
              <div className="viewer-edit-actions">
                <button
                  type="button"
                  className={`secondary-button edit-toggle ${isEditing ? "active" : ""}`}
                  onClick={() => setIsEditing((value) => !value)}
                >
                  <Pencil size={16} />
                  {isEditing ? "Завершить редактирование" : "Редактировать точки"}
                </button>

                <button
                  type="button"
                  className="secondary-button"
                  onClick={handleUndo}
                  disabled={!isEditing || undoStack.length === 0}
                >
                  <Undo2 size={16} />
                  Отменить
                </button>

                <button
                  type="button"
                  className="secondary-button"
                  onClick={handleResetPlacements}
                  disabled={!hasUnsavedChanges}
                >
                  <RotateCcw size={16} />
                  Сбросить
                </button>
              </div>

              {isEditing && (
                <p className="viewer-edit-hint">
                  Перетаскивай точки посадки мышью, затем нажми «Сохранить изменения».
                </p>
              )}

              {saveMessage && (
                <p className="viewer-edit-warning" role="status">
                  {saveMessage}
                </p>
              )}

              {hasUnsavedChanges && (
                <p className="viewer-edit-warning" role="status">
                  Есть несохранённые изменения. Скачивание временно отключено, чтобы не выдать исходный DXF вместо отредактированного.
                </p>
              )}
            </div>}

            {viewerMode === "2d" ? (
              <PlanViewer
                result={{ ...result, placements }}
                selected={selected}
                onSelect={setSelected}
                isEditing={isEditing}
                onMove={handleMovePlacement}
                onDragStart={handleDragStart}
              />
            ) : (
              <ThreeDViewer result={{ ...result, placements: placements }} />
            )}
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
              onClick={() => void handleSaveEdits()}
              disabled={!hasUnsavedChanges || saving || downloading !== null}
            >
              <Save size={17} />
              {saving ? "Сохранение…" : "Сохранить изменения"}
            </button>

            <button
              className="secondary-button full"
              type="button"
              onClick={() => void handleDownloadOriginalDxf()}
              disabled={downloading !== null}
            >
              <Download size={17} />
              {downloading === "dxf" ? "Подготовка…" : "Скачать исходный DXF"}
            </button>

            <button
              className="secondary-button full"
              type="button"
              onClick={() => void handleDownloadEditedDxf()}
              disabled={downloading !== null || !hasSavedEdits}
              title={!hasSavedEdits ? "Сначала сохраните пользовательские изменения" : "Скачать последнюю сохранённую редакцию"}
            >
              <Download size={17} />
              {downloading === "edited-dxf" ? "Подготовка…" : "Скачать отредактированный DXF"}
            </button>

            <button
              className="secondary-button full"
              type="button"
              onClick={
                handleDownloadReport
              }
              disabled={
                downloading !== null || hasUnsavedChanges
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
