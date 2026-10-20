import { Download, FileJson, ImageIcon, Layers, MousePointer2, Move, Plus, RotateCcw, Save, Undo2, X } from "lucide-react";
import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError, checkPoint, download, saveEdits, validateEdits } from "../api";
import LayersPanel from "../components/LayersPanel";
import NormsPanel from "../components/NormsPanel";
import PlanCanvas, { type Mode, type Visibility } from "../components/PlanCanvas";
import PointPanel from "../components/PointPanel";
import RejectionsPanel from "../components/RejectionsPanel";
import VisualPanel from "../components/VisualPanel";
import { GROUP_LABEL, area, count, num, type LayerGroup, lowerFirst } from "../format";
import type { CheckResult, EditIssue, EditsPayload, Placement, PlanResult, Rule, Species } from "../types";

const Scene3D = lazy(() => import("../components/Scene3D"));

type Tab = "norms" | "point" | "rejections" | "layers";

interface Props {
  result: PlanResult;
  busy: boolean;
  onApplyLayers: (overrides: Record<string, string>, boundaryLayer: string | null) => void;
  onRestart: () => void;
}

const GROUPS = Object.keys(GROUP_LABEL) as LayerGroup[];
const HISTORY_LIMIT = 60;
const CHECK_INTERVAL_MS = 140;

function round(value: number) {
  return Math.round(value * 1000) / 1000;
}

export default function ResultScreen({ result, busy, onApplyLayers, onRestart }: Props) {
  const rulesById = useMemo<Record<string, Rule>>(
    () => Object.fromEntries(result.rules.map((rule) => [rule.rule_id, rule])),
    [result.rules],
  );

  const [placements, setPlacements] = useState<Placement[]>(result.placements);
  const [saved, setSaved] = useState<Placement[]>(result.placements);
  const [hasSavedEdits, setHasSavedEdits] = useState(result.has_saved_edits);
  const [history, setHistory] = useState<Placement[][]>([]);
  const [issues, setIssues] = useState<EditIssue[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [check, setCheck] = useState<CheckResult | null>(null);
  const [checkLoading, setCheckLoading] = useState(false);
  const [checkError, setCheckError] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>("view");
  const [view, setView] = useState<"2d" | "3d">("2d");
  const [tab, setTab] = useState<Tab>("norms");
  const [visibility, setVisibility] = useState<Visibility>({
    tree: true,
    shrub: true,
    rejections: false,
    tight: false,
    lawn: true,
    scene: true,
    groups: Object.fromEntries(GROUPS.map((group) => [group, true])) as Record<LayerGroup, boolean>,
  });
  const [rejectionRule, setRejectionRule] = useState<string | null>(null);
  const [focus, setFocus] = useState<{ x: number; y: number; nonce: number } | null>(null);
  const [notice, setNotice] = useState<{ tone: "ok" | "stop"; text: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [bannerHidden, setBannerHidden] = useState(false);
  const [layersOpen, setLayersOpen] = useState(false);
  const [visualOpen, setVisualOpen] = useState(false);
  const counter = useRef(0);
  const dragging = useRef(false);

  const savedById = useMemo(() => new Map(saved.map((p) => [p.id, p])), [saved]);
  const selected = useMemo(() => placements.find((p) => p.id === selectedId) ?? null, [placements, selectedId]);

  const payload = useMemo<EditsPayload>(() => {
    const present = new Set<string>();
    const moved: EditsPayload["placements"] = [];
    const added: EditsPayload["added"] = [];
    for (const p of placements) {
      present.add(p.id);
      const before = savedById.get(p.id);
      if (!before) added.push({ id: p.id, x: p.x, y: p.y, species_type: p.species_type });
      else if (before.x !== p.x || before.y !== p.y) moved.push({ id: p.id, x: p.x, y: p.y });
    }
    const removed = saved.filter((p) => !present.has(p.id)).map((p) => p.id);
    return { placements: moved, added, removed };
  }, [placements, saved, savedById]);

  const changeCount = payload.placements.length + payload.added.length + payload.removed.length;
  const dirty = changeCount > 0;
  const issueIds = useMemo(() => new Set(issues.map((issue) => issue.id)), [issues]);
  const counts = useMemo(() => {
    let trees = 0;
    for (const p of placements) if (p.species_type === "tree") trees++;
    return { trees, shrubs: placements.length - trees };
  }, [placements]);

  useEffect(() => {
    if (!dirty) {
      setIssues([]);
      return;
    }
    if (dragging.current) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      validateEdits(result.run_id, payload, controller.signal)
        .then((response) => setIssues(response.issues))
        .catch((error) => {
          if (error instanceof DOMException && error.name === "AbortError") return;
          setNotice({ tone: "stop", text: error instanceof Error ? error.message : "Проверка правок не выполнена" });
        });
    }, 300);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [payload, dirty, result.run_id]);

  useEffect(() => {
    if (notice?.tone !== "ok") return;
    const timer = window.setTimeout(() => setNotice(null), 6000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const lastCheck = useRef(0);
  useEffect(() => {
    if (!selected) {
      setCheck(null);
      setCheckError(null);
      return;
    }
    const controller = new AbortController();
    const wait = Math.max(0, CHECK_INTERVAL_MS - (performance.now() - lastCheck.current));
    setCheckLoading(true);
    const timer = window.setTimeout(() => {
      lastCheck.current = performance.now();
      checkPoint(
        result.run_id,
        { x: selected.x, y: selected.y, species_type: selected.species_type, id: selected.id },
        controller.signal,
      )
        .then((response) => {
          setCheck(response);
          setCheckError(null);
          setCheckLoading(false);
        })
        .catch((error) => {
          if (error instanceof DOMException && error.name === "AbortError") return;
          setCheckError(error instanceof Error ? error.message : "Проверка не выполнена");
          setCheckLoading(false);
        });
    }, wait);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [selected?.id, selected?.x, selected?.y, selected?.species_type, result.run_id]);

  useEffect(() => {
    setCheck(null);
  }, [selectedId]);

  const remember = useCallback(() => {
    setHistory((stack) => [...stack.slice(-(HISTORY_LIMIT - 1)), placements]);
  }, [placements]);

  const select = useCallback((id: string | null) => {
    setSelectedId(id);
    if (id) setTab("point");
  }, []);

  const move = useCallback((id: string, x: number, y: number) => {
    setPlacements((current) => current.map((p) => (p.id === id ? { ...p, x: round(x), y: round(y) } : p)));
  }, []);

  const add = useCallback(
    (species: Species, x: number, y: number) => {
      remember();
      counter.current += 1;
      const id = `${species}-u${Date.now().toString(36)}${counter.current}`;
      setPlacements((current) => [...current, { id, x: round(x), y: round(y), species_type: species, tightest: null }]);
      select(id);
    },
    [remember, select],
  );

  const remove = useCallback(
    (id: string) => {
      remember();
      setPlacements((current) => current.filter((p) => p.id !== id));
      setSelectedId(null);
    },
    [remember],
  );

  const undo = useCallback(() => {
    if (history.length === 0) return;
    setPlacements(history[history.length - 1]);
    setHistory((stack) => stack.slice(0, -1));
  }, [history]);

  const reset = () => {
    setPlacements(saved);
    setHistory([]);
    setIssues([]);
    setNotice(null);
  };

  const save = async () => {
    if (!dirty || saving) return;
    setSaving(true);
    setNotice(null);
    try {
      const response = await saveEdits(result.run_id, payload);
      setPlacements(response.placements);
      setSaved(response.placements);
      setHistory([]);
      setIssues([]);
      setHasSavedEdits(true);
      setNotice({ tone: "ok", text: `Сохранено: ${count(changeCount, ["правка", "правки", "правок"])}. Расчётный DXF не изменён, правки — в отдельном файле.` });
    } catch (error) {
      if (error instanceof ApiError && error.issues.length > 0) setIssues(error.issues);
      setNotice({ tone: "stop", text: error instanceof Error ? error.message : "Не удалось сохранить" });
    } finally {
      setSaving(false);
    }
  };

  const fetchFile = async (kind: "original-dxf" | "edited-dxf" | "report") => {
    setDownloading(kind);
    try {
      await download(result.run_id, kind);
    } catch (error) {
      setNotice({ tone: "stop", text: error instanceof Error ? error.message : "Не удалось скачать" });
    } finally {
      setDownloading(null);
    }
  };

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName)) return;
      if (event.key === "Escape") {
        setSelectedId(null);
        setMode("view");
      } else if ((event.key === "Delete" || event.key === "Backspace") && mode !== "view" && selectedId) {
        event.preventDefault();
        remove(selectedId);
      } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
        event.preventDefault();
        undo();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mode, selectedId, remove, undo]);

  const showRule = (ruleId: string | null) => {
    setRejectionRule(ruleId);
    setVisibility((v) => ({ ...v, rejections: ruleId !== null ? true : v.rejections }));
  };

  const focusOn = (x: number, y: number) => setFocus({ x, y, nonce: Date.now() });

  const unresolved = result.layers.filter((layer) => layer.kind === null).length;
  const selectedIssues = selected ? issues.filter((issue) => issue.id === selected.id) : [];
  const summary = result.summary;

  return (
    <div className="result">
      <header className="topbar">
        <div className="brand">Зелёный план</div>
        <div className="topbar-file">
          <span className="mono">{result.filename}</span>
          <span className="muted">
            граница: {result.site.method_label}
            {result.site.outliers > 0 && `, без ${count(result.site.outliers, ["выброса", "выбросов", "выбросов"])}`}
          </span>
        </div>
        <div className="topbar-actions">
          <button type="button" className="secondary-button" disabled={downloading !== null} onClick={() => fetchFile("original-dxf")}>
            <Download size={15} />
            {downloading === "original-dxf" ? "Готовим DXF…" : "DXF"}
          </button>
          <button
            type="button"
            className="secondary-button"
            disabled={downloading !== null || !hasSavedEdits || dirty}
            title={!hasSavedEdits ? "Появится после сохранения правок" : dirty ? "Сначала сохраните правки" : undefined}
            onClick={() => fetchFile("edited-dxf")}
          >
            <Download size={15} />
            {downloading === "edited-dxf" ? "Готовим DXF…" : "DXF с правками"}
          </button>
          <button
            type="button"
            className="secondary-button"
            disabled={downloading !== null || dirty}
            title="Каждая посадка с проверкой по всем нормам"
            onClick={() => fetchFile("report")}
          >
            <FileJson size={15} />
            Обоснование
          </button>
          <button type="button" className="ghost-button" onClick={onRestart}>
            Новый файл
          </button>
        </div>
      </header>

      <dl className="summary">
        <div>
          <dt>деревья</dt>
          <dd>{num(counts.trees)}</dd>
        </div>
        <div>
          <dt>кустарники</dt>
          <dd>{num(counts.shrubs)}</dd>
        </div>
        <div>
          <dt>газоны</dt>
          <dd>{area(summary.lawn_m2 ?? 0)}</dd>
        </div>
        <div>
          <dt>живые изгороди</dt>
          <dd>{num(summary.hedges_m ?? 0)} м</dd>
        </div>
        <div>
          <dt>цветники</dt>
          <dd>{num(summary.flowerbeds ?? 0)}</dd>
        </div>
        <div>
          <dt>отклонено точек</dt>
          <dd>{num(summary.rejections)}</dd>
        </div>
        <div>
          <dt>участок</dt>
          <dd>{area(summary.area_m2)}</dd>
        </div>
        <div>
          <dt>объектов учтено</dt>
          <dd>{num(summary.features)}</dd>
        </div>
        <div>
          <dt>слоёв</dt>
          <dd>
            {num(summary.layers_total)}
            {unresolved > 0 && <small> · {num(unresolved)} без типа</small>}
          </dd>
        </div>
        <div>
          <dt>расчёт</dt>
          <dd>{num(summary.duration_s, 1)} с</dd>
        </div>
      </dl>

      <div className="workspace">
        <section className="plan">
          <div className="plan-toolbar">
            <div className="segmented" role="tablist" aria-label="Вид">
              <button type="button" role="tab" aria-selected={view === "2d"} className={view === "2d" ? "on" : ""} onClick={() => setView("2d")}>
                План
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={view === "3d"}
                className={view === "3d" ? "on" : ""}
                onClick={() => {
                  setView("3d");
                  setMode("view");
                }}
              >
                3D
              </button>
            </div>

            {view === "2d" && (
              <div className="segmented" aria-label="Инструмент">
                <button type="button" className={mode === "view" ? "on" : ""} onClick={() => setMode("view")} title="Просмотр (Esc)">
                  <MousePointer2 size={14} />
                  Выбор
                </button>
                <button type="button" className={mode === "move" ? "on" : ""} onClick={() => setMode("move")} title="Перетаскивать посадки">
                  <Move size={14} />
                  Перемещать
                </button>
                <button type="button" className={mode === "add-tree" ? "on" : ""} onClick={() => setMode("add-tree")}>
                  <Plus size={14} />
                  Дерево
                </button>
                <button type="button" className={mode === "add-shrub" ? "on" : ""} onClick={() => setMode("add-shrub")}>
                  <Plus size={14} />
                  Кустарник
                </button>
              </div>
            )}

            {view === "2d" && (
              <div className="toolbar-group">
                <button type="button" className="icon-button" title="Отменить (Ctrl+Z)" disabled={history.length === 0} onClick={undo}>
                  <Undo2 size={16} />
                </button>
                <button type="button" className="icon-button" title="Вернуть сохранённое" disabled={!dirty} onClick={reset}>
                  <RotateCcw size={16} />
                </button>
              </div>
            )}

            {view === "3d" && (
              <button
                type="button"
                className={`secondary-button ${visualOpen ? "on" : ""}`}
                onClick={() => setVisualOpen((v) => !v)}
              >
                <ImageIcon size={15} />
                ИИ-визуализация
              </button>
            )}

            <div className="toolbar-spacer" />

            <div className="legend">
              <label className={`legend-item ${visibility.tree ? "" : "off"}`}>
                <input type="checkbox" checked={visibility.tree} onChange={(e) => setVisibility((v) => ({ ...v, tree: e.target.checked }))} />
                <span className="swatch swatch-tree" />
                деревья
              </label>
              <label className={`legend-item ${visibility.shrub ? "" : "off"}`}>
                <input type="checkbox" checked={visibility.shrub} onChange={(e) => setVisibility((v) => ({ ...v, shrub: e.target.checked }))} />
                <span className="swatch swatch-shrub" />
                кустарники
              </label>
              <label className={`legend-item ${visibility.lawn ? "" : "off"}`}>
                <input type="checkbox" checked={visibility.lawn} onChange={(e) => setVisibility((v) => ({ ...v, lawn: e.target.checked }))} />
                <span className="swatch swatch-lawn" />
                газоны
              </label>
              <label className={`legend-item ${visibility.scene ? "" : "off"}`}>
                <input type="checkbox" checked={visibility.scene} onChange={(e) => setVisibility((v) => ({ ...v, scene: e.target.checked }))} />
                <span className="swatch swatch-hedge" />
                изгороди, цветники
              </label>
              <label className={`legend-item ${visibility.tight ? "" : "off"}`}>
                <input type="checkbox" checked={visibility.tight} onChange={(e) => setVisibility((v) => ({ ...v, tight: e.target.checked }))} />
                <span className="swatch swatch-tight" />
                запас &lt; 0,5 м
              </label>
              <label className={`legend-item ${visibility.rejections ? "" : "off"}`}>
                <input
                  type="checkbox"
                  checked={visibility.rejections}
                  onChange={(e) => {
                    setVisibility((v) => ({ ...v, rejections: e.target.checked }));
                    if (!e.target.checked) setRejectionRule(null);
                  }}
                />
                <span className="swatch swatch-reject" />
                {rejectionRule ? `отказы: ${lowerFirst(rulesById[rejectionRule]?.object_label ?? "")}` : "отказы"}
              </label>
              <div className="layers-popover">
                <button type="button" className={`icon-button ${layersOpen ? "on" : ""}`} title="Слои подосновы" onClick={() => setLayersOpen((v) => !v)}>
                  <Layers size={16} />
                </button>
                {layersOpen && (
                  <div className="popover">
                    <p className="popover-title">Подоснова</p>
                    {GROUPS.map((group) => (
                      <label key={group} className="popover-row">
                        <input
                          type="checkbox"
                          checked={visibility.groups[group]}
                          onChange={(e) =>
                            setVisibility((v) => ({ ...v, groups: { ...v.groups, [group]: e.target.checked } }))
                          }
                        />
                        <span className={`swatch swatch-${group}`} />
                        {GROUP_LABEL[group]}
                      </label>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="plan-stage">
            {view === "2d" ? (
              <PlanCanvas
                features={result.features}
                greening={result.greening}
                site={result.site.geometry}
                placements={placements}
                rejections={result.rejections}
                rejectionRule={rejectionRule}
                visibility={visibility}
                selectedId={selectedId}
                checks={check?.checks ?? null}
                rulesById={rulesById}
                issueIds={issueIds}
                mode={mode}
                focus={focus}
                onSelect={select}
                onDragStart={() => {
                  dragging.current = true;
                  remember();
                }}
                onDrag={move}
                onDragEnd={(id, x, y) => {
                  dragging.current = false;
                  move(id, x, y);
                }}
                onAdd={add}
              />
            ) : (
              <Suspense fallback={<div className="scene-loading">Загружаем 3D…</div>}>
                <Scene3D features={result.features} site={result.site.geometry} placements={placements} greening={result.greening} />
              </Suspense>
            )}
            {view === "3d" && visualOpen && (
              <VisualPanel runId={result.run_id} filename={result.filename} onClose={() => setVisualOpen(false)} />
            )}
            {(dirty || notice) && (
              <div className={`edit-bar ${issues.length > 0 ? "has-issues" : ""}`}>
                {dirty ? (
                  <>
                    <span>
                      {count(changeCount, ["правка", "правки", "правок"])}
                      {issues.length > 0 ? (
                        <span className="edit-issues">
                          {" "}
                          · {count(issueIds.size, ["точка нарушает", "точки нарушают", "точек нарушают"])} нормы:{" "}
                          {issues.slice(0, 3).map((issue, index) => (
                            <button
                              key={`${issue.id}-${issue.code}`}
                              type="button"
                              className="link-button"
                              onClick={() => {
                                const target = placements.find((p) => p.id === issue.id);
                                select(issue.id);
                                if (target) focusOn(target.x, target.y);
                              }}
                            >
                              {index > 0 ? "; " : ""}
                              {issue.message}
                            </button>
                          ))}
                          {issues.length > 3 && ` и ещё ${issues.length - 3}`}
                        </span>
                      ) : (
                        <span className="muted"> · нарушений нет</span>
                      )}
                    </span>
                    <button type="button" className="primary-button" disabled={saving || issues.length > 0} onClick={save}>
                      <Save size={15} />
                      {saving ? "Сохраняем…" : "Сохранить в DXF"}
                    </button>
                  </>
                ) : (
                  notice && (
                    <>
                      <span className={`tone-text-${notice.tone}`}>{notice.text}</span>
                      <button type="button" className="icon-button" title="Скрыть" onClick={() => setNotice(null)}>
                        <X size={15} />
                      </button>
                    </>
                  )
                )}
              </div>
            )}

            {view === "2d" && mode !== "view" && !dirty && (
              <p className="plan-hint">
                {mode === "move"
                  ? "Перетащите посадку. Размерные линии покажут расстояния до ближайших объектов. Delete — удалить выбранную."
                  : "Щёлкните по плану, чтобы поставить посадку. Проверка по нормам — сразу после установки."}
              </p>
            )}
          </div>
        </section>

        <aside className="side">
          {unresolved > 0 && !bannerHidden && (
            <div className="banner">
              <p>
                {count(unresolved, ["слой не распознан", "слоя не распознаны", "слоёв не распознаны"])} — объекты с них не проверяются.
              </p>
              <button type="button" className="link-button" onClick={() => setTab("layers")}>
                Назначить типы
              </button>
              <button type="button" className="icon-button" title="Скрыть" onClick={() => setBannerHidden(true)}>
                <X size={14} />
              </button>
            </div>
          )}

          <nav className="tabs" role="tablist">
            <button type="button" role="tab" aria-selected={tab === "norms"} className={tab === "norms" ? "on" : ""} onClick={() => setTab("norms")}>
              Нормы
            </button>
            <button type="button" role="tab" aria-selected={tab === "point"} className={tab === "point" ? "on" : ""} onClick={() => setTab("point")}>
              Точка
            </button>
            <button type="button" role="tab" aria-selected={tab === "rejections"} className={tab === "rejections" ? "on" : ""} onClick={() => setTab("rejections")}>
              Отказы <span className="tab-count">{num(result.rejections.length)}</span>
            </button>
            <button type="button" role="tab" aria-selected={tab === "layers"} className={tab === "layers" ? "on" : ""} onClick={() => setTab("layers")}>
              Слои {unresolved > 0 && <span className="tab-count warn">{num(unresolved)}</span>}
            </button>
          </nav>

          <div className="side-scroll">
            {tab === "norms" && (
              <NormsPanel rules={result.rules} pending={result.pending_rules} greening={result.greening} activeRule={rejectionRule} onShowRejections={showRule} />
            )}
            {tab === "point" && (
              <PointPanel
                placement={selected}
                check={check}
                loading={checkLoading}
                error={checkError}
                rulesById={rulesById}
                issues={selectedIssues}
                editable={view === "2d" && mode !== "view"}
                isNew={selected !== null && !savedById.has(selected.id)}
                onRemove={remove}
              />
            )}
            {tab === "rejections" && (
              <RejectionsPanel
                rejections={result.rejections}
                rulesById={rulesById}
                activeRule={rejectionRule}
                onShowRule={showRule}
                onFocus={(x, y) => {
                  setVisibility((v) => ({ ...v, rejections: true }));
                  focusOn(x, y);
                }}
              />
            )}
            {tab === "layers" && (
              <LayersPanel
                layers={result.layers}
                kinds={result.allowed_kinds}
                overrides={result.overrides}
                boundaryLayer={result.boundary_layer}
                siteLabel={result.site.method_label}
                busy={busy}
                onApply={onApplyLayers}
              />
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
