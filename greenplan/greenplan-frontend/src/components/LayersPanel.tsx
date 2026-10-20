import { RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";

import { METHOD_LABEL, count, num } from "../format";
import type { KindOption, LayerInfo } from "../types";

interface Props {
  layers: LayerInfo[];
  kinds: KindOption[];
  overrides: Record<string, string>;
  boundaryLayer: string | null;
  siteLabel?: string;
  busy: boolean;
  onApply: (overrides: Record<string, string>, boundaryLayer: string | null) => void;
}

const UNSET = "";

function breakable(name: string) {
  const parts = name.split(/(?<=[_\-.])/);
  return parts.map((part, index) => (
    <span key={index}>
      {part}
      {index < parts.length - 1 && <wbr />}
    </span>
  ));
}

function entityTypes(types: Record<string, number>): string {
  return Object.entries(types)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 2)
    .map(([type]) => type)
    .join(", ");
}

export default function LayersPanel({ layers, kinds, overrides, boundaryLayer, siteLabel, busy, onApply }: Props) {
  const unresolved = layers.filter((layer) => layer.kind === null);
  const [onlyUnresolved, setOnlyUnresolved] = useState(unresolved.length > 0);
  const [draft, setDraft] = useState<Record<string, string>>(overrides);
  const [boundary, setBoundary] = useState<string>(boundaryLayer ?? UNSET);
  const [query, setQuery] = useState("");

  const original = useMemo(() => new Map(layers.map((layer) => [layer.layer, layer.kind ?? UNSET])), [layers]);

  const changes = useMemo(() => {
    const result: Record<string, string> = {};
    for (const [layer, kind] of Object.entries(draft)) {
      if (kind !== UNSET) result[layer] = kind;
    }
    return result;
  }, [draft]);

  const dirty =
    JSON.stringify(Object.entries(changes).sort()) !== JSON.stringify(Object.entries(overrides).sort()) ||
    (boundary || null) !== (boundaryLayer || null);

  const visible = layers.filter((layer) => {
    if (onlyUnresolved && layer.kind !== null && !(layer.layer in draft)) return false;
    if (query && !layer.layer.toLowerCase().includes(query.toLowerCase())) return false;
    return true;
  });

  const setKind = (layer: string, kind: string) => {
    setDraft((current) => {
      const next = { ...current };
      if (kind === UNSET || (kind === original.get(layer) && !(layer in overrides))) delete next[layer];
      else next[layer] = kind;
      return next;
    });
  };

  return (
    <div className="panel-body layers-panel">
      <div className="lede">
        {unresolved.length > 0 ? (
          <p>
            {count(unresolved.length, ["слой не распознан", "слоя не распознаны", "слоёв не распознаны"])}. Объекты с них не участвуют в
            проверке норм. Если на слое сети или здания, назначьте тип и пересчитайте план.
          </p>
        ) : (
          <p>Все слои распознаны. Тип любого слоя можно поправить вручную.</p>
        )}
      </div>

      <label className="field">
        <span className="field-label">Граница участка</span>
        <select value={boundary} onChange={(event) => setBoundary(event.target.value)}>
          <option value={UNSET}>Автоматически</option>
          {layers.map((layer) => (
            <option key={layer.layer} value={layer.layer}>
              {layer.layer}
            </option>
          ))}
        </select>
        <span className="field-hint">
          {siteLabel ? `Сейчас: ${siteLabel}. ` : ""}Укажите слой с замкнутым контуром, если граница захватила лишнее.
        </span>
      </label>

      <div className="layers-tools">
        <input
          type="search"
          placeholder="Поиск слоя"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <label className="check">
          <input type="checkbox" checked={onlyUnresolved} onChange={(event) => setOnlyUnresolved(event.target.checked)} />
          только нераспознанные
        </label>
      </div>

      <div className="layers-table-wrap">
        <table className="layers-table">
          <thead>
            <tr>
              <th>Слой</th>
              <th className="num">Объектов</th>
              <th>Тип</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((layer) => {
              const value = draft[layer.layer] ?? layer.kind ?? UNSET;
              const changed = layer.layer in draft;
              return (
                <tr key={layer.layer} className={layer.kind === null && !changed ? "is-unresolved" : changed ? "is-changed" : ""}>
                  <td>
                    <span className="layer-name">{breakable(layer.layer)}</span>
                    <span className="layer-meta">
                      {changed ? "изменено" : METHOD_LABEL[layer.method] ?? layer.method}
                      {" · "}
                      {entityTypes(layer.entity_types)}
                      {(layer.typed_by_block ?? 0) > 0 && <> · по именам блоков: {num(layer.typed_by_block ?? 0)}</>}
                    </span>
                  </td>
                  <td className="num mono">{num(layer.entity_count)}</td>
                  <td>
                    <select value={value} onChange={(event) => setKind(layer.layer, event.target.value)} aria-label={`Тип слоя ${layer.layer}`}>
                      <option value={UNSET}>— не распознан</option>
                      {kinds.map((kind) => (
                        <option key={kind.value} value={kind.value}>
                          {kind.label}
                        </option>
                      ))}
                    </select>
                  </td>
                </tr>
              );
            })}
            {visible.length === 0 && (
              <tr>
                <td colSpan={3} className="muted small">
                  Ничего не найдено
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="layers-footer">
        <span className="muted small">
          {Object.keys(changes).length > 0 ? `Вручную: ${count(Object.keys(changes).length, ["слой", "слоя", "слоёв"])}` : "Ручных назначений нет"}
        </span>
        <button
          type="button"
          className="primary-button"
          disabled={!dirty || busy}
          onClick={() => onApply(changes, boundary || null)}
        >
          <RefreshCw size={15} />
          Пересчитать
        </button>
      </div>
    </div>
  );
}
