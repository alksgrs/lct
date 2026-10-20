import { FileUp } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { API_URL, fetchRules } from "../api";
import { normValue, lowerFirst } from "../format";
import type { Rule, RulesCatalog } from "../types";

interface Props {
  busy: boolean;
  onStart: (file: File) => void;
}

interface Row {
  label: string;
  tree: Rule | undefined;
  shrub: Rule | undefined;
  ban: Rule | undefined;
}

function rows(catalog: RulesCatalog): Row[] {
  const map = new Map<string, Row>();
  for (const rule of catalog.rules) {
    const row = map.get(rule.object) ?? { label: rule.object_label, tree: undefined, shrub: undefined, ban: undefined };
    if (rule.kind === "ban") row.ban = rule;
    else if (rule.planting === "tree") row.tree = rule;
    else if (rule.planting === "shrub") row.shrub = rule;
    map.set(rule.object, row);
  }
  return [...map.values()];
}

function cell(rule: Rule | undefined) {
  if (!rule) return <td className="num muted">—</td>;
  if (rule.kind === "not_regulated") return <td className="num muted">н/н</td>;
  return <td className="num mono">{rule.min_distance_m === null ? "—" : normValue(rule.min_distance_m)}</td>;
}

export default function UploadScreen({ busy, onStart }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [catalog, setCatalog] = useState<RulesCatalog | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);

  useEffect(() => {
    fetchRules()
      .then(setCatalog)
      .catch((error: Error) => setCatalogError(error.message));
  }, []);

  const take = (files: FileList | null) => {
    const file = files?.[0];
    if (file) onStart(file);
  };

  const table = catalog ? rows(catalog) : [];
  const distances = table.filter((row) => !row.ban);
  const bans = table.filter((row) => row.ban);

  return (
    <main className="upload">
      <section className="upload-main">
        <h1>План озеленения по подоснове</h1>
        <p className="upload-lede">
          Загрузите DXF с сетями, зданиями и покрытиями. Сервис расставит деревья и кустарники с учётом отступов, запишет их
          на слои <code>PLANTING_TREES</code> и <code>PLANTING_SHRUBS</code> и покажет, по какой норме прошла каждая точка.
        </p>

        <div
          className={`dropzone ${over ? "is-over" : ""} ${busy ? "is-busy" : ""}`}
          onDragOver={(event) => {
            event.preventDefault();
            setOver(true);
          }}
          onDragLeave={() => setOver(false)}
          onDrop={(event) => {
            event.preventDefault();
            setOver(false);
            if (!busy) take(event.dataTransfer.files);
          }}
        >
          <FileUp size={22} strokeWidth={1.5} />
          <div>
            <strong>{busy ? "Загружаем…" : "Перетащите DXF сюда"}</strong>
            <span>или выберите файл, до 200 МБ</span>
          </div>
          <button type="button" className="primary-button" disabled={busy} onClick={() => input.current?.click()}>
            Выбрать файл
          </button>
          <input
            ref={input}
            type="file"
            accept=".dxf"
            hidden
            onChange={(event) => {
              take(event.target.files);
              event.target.value = "";
            }}
          />
        </div>

        <ul className="upload-notes">
          <li>Слои распознаются по названию: шаблоны, словарь сокращений, нечёткое сравнение. Нераспознанные можно назначить вручную после расчёта.</li>
          <li>Граница участка берётся со слоя границы; если его нет — по контуру объектов чертежа.</li>
          <li>Исходный DXF не меняется: посадки пишутся в копию.</li>
        </ul>
      </section>

      <aside className="upload-rules">
        <h2>Что проверяется</h2>
        {catalogError && (
          <p className="muted small">
            Справочник норм не загрузился: {catalogError}. Адрес сервера: <code>{API_URL}</code>
          </p>
        )}
        {catalog && (
          <>
            <p className="muted small">Расстояние от оси посадки до объекта, не менее, м</p>
            <table className="rules-table">
              <thead>
                <tr>
                  <th>Объект</th>
                  <th className="num">Дерево</th>
                  <th className="num">Кустарник</th>
                </tr>
              </thead>
              <tbody>
                {distances.map((row) => (
                  <tr key={row.label}>
                    <td>{row.label}</td>
                    {cell(row.tree)}
                    {cell(row.shrub)}
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="source-line">ППМ 743-ПП, прил. 1, п. 3.6.3, табл. 3.6.1 (МГСН 1.01-99). н/н — не нормируется.</p>

            <p className="muted small">Охранные зоны ВЛ, посадка запрещена, м</p>
            <table className="rules-table">
              <tbody>
                {bans.map((row) => (
                  <tr key={row.label}>
                    <td>{row.label}</td>
                    <td className="num mono">{row.ban!.zone_m === null ? "—" : normValue(row.ban!.zone_m)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="source-line">ПП РФ № 160 от 24.02.2009, Правила п. 10 «в», Приложение «а».</p>
            {catalog.pending_rules.length > 0 && (
              <p className="muted small">
                Ждут сверки и пока не применяются: {catalog.pending_rules.map((rule) => lowerFirst(rule.object_label)).join(", ")}.
              </p>
            )}
          </>
        )}
      </aside>
    </main>
  );
}
