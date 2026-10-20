import { Trash2 } from "lucide-react";
import { useState } from "react";

import { PLANTING_LABEL, SPECIES_NAME, TIGHT_MARGIN_M, marginTone, meters, num, ruleNorm, lowerFirst } from "../format";
import type { Check, CheckResult, EditIssue, Placement, Rule } from "../types";
import MarginBar from "./MarginBar";

const FAR_M = 50;

interface Props {
  placement: Placement | null;
  check: CheckResult | null;
  loading: boolean;
  error: string | null;
  rulesById: Record<string, Rule>;
  issues: EditIssue[];
  editable: boolean;
  isNew: boolean;
  onRemove: (id: string) => void;
}

function CheckRow({ check, rule }: { check: Check; rule: Rule }) {
  const [open, setOpen] = useState(false);
  const regulated = rule.kind !== "not_regulated";
  const tone = check.status === "violated" || check.status === "banned_zone" ? "stop" : regulated ? marginTone(check.margin_m) : "none";
  return (
    <li className={`check-row tone-${tone}`}>
      <button type="button" className="check-head" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <span className="check-title">{rule.object_label}</span>
        <span className="check-distance">{meters(check.distance_m)}</span>
      </button>
      <div className="check-line">
        {regulated ? <MarginBar distance={check.distance_m} limit={rule.limit_m} /> : <span className="margin-bar margin-bar-empty" />}
        <span className="check-norm">
          {rule.kind === "ban" && check.status === "banned_zone" ? "в охранной зоне" : ruleNorm(rule)}
          {regulated && check.margin_m !== null && check.status === "allowed" && <> · запас {num(check.margin_m, 2)}</>}
        </span>
      </div>
      {open && (
        <div className="norm-source">
          <span>{rule.act}</span>
          <span>{rule.clause}</span>
          {rule.note && <span className="norm-note">{rule.note}</span>}
          {rule.source_url && (
            <a href={rule.source_url} target="_blank" rel="noreferrer">
              Текст акта
            </a>
          )}
        </div>
      )}
    </li>
  );
}

export default function PointPanel({ placement, check, loading, error, rulesById, issues, editable, isNew, onRemove }: Props) {
  if (!placement) {
    return (
      <div className="panel-body">
        <div className="empty">
          <p>Выберите посадку на плане.</p>
          <p className="muted">
            Здесь будет проверка точки по каждой норме: расстояние до ближайшего объекта, требование и пункт
            нормативного акта. На плане появятся размерные линии до этих объектов.
          </p>
        </div>
      </div>
    );
  }

  const checks = (check?.checks ?? []).filter((c) => rulesById[c.rule_id]);
  const measured = checks
    .filter((c) => c.status !== "not_applicable")
    .sort((a, b) => {
      const ra = rulesById[a.rule_id];
      const rb = rulesById[b.rule_id];
      const ma = ra.kind === "not_regulated" ? Infinity : a.margin_m ?? Infinity;
      const mb = rb.kind === "not_regulated" ? Infinity : b.margin_m ?? Infinity;
      return ma - mb;
    });
  const near = measured.filter((c) => (c.status !== "allowed" && c.status !== "not_regulated") || (c.distance_m ?? 0) <= FAR_M);
  const far = measured.filter((c) => !near.includes(c));
  const absent = checks.filter((c) => c.status === "not_applicable");
  const broken = measured.filter((c) => c.status === "violated" || c.status === "banned_zone");
  const tight = measured.filter((c) => c.status === "allowed" && (c.margin_m ?? Infinity) < TIGHT_MARGIN_M);

  let verdict: { tone: string; text: string };
  if (issues.length > 0) verdict = { tone: "stop", text: issues.map((i) => i.message).join(". ") };
  else if (check && !check.inside_site) verdict = { tone: "stop", text: "Точка за границей участка" };
  else if (check?.inside_maf) verdict = { tone: "stop", text: "Точка внутри малой архитектурной формы" };
  else if (broken.length > 0) verdict = { tone: "stop", text: `Нарушено норм: ${broken.length}` };
  else if (tight.length > 0) verdict = { tone: "tight", text: `Нормы соблюдены, запас меньше ${num(TIGHT_MARGIN_M, 1)} м` };
  else verdict = { tone: "ok", text: "Нормы соблюдены" };

  return (
    <div className="panel-body">
      <div className="point-head">
        <div>
          <h3>
            {SPECIES_NAME[placement.species_type]}
            {isNew && <span className="tag">добавлено</span>}
          </h3>
          <p className="mono muted small">
            {placement.id} · x {num(placement.x, 2)} · y {num(placement.y, 2)}
          </p>
        </div>
        {editable && (
          <button type="button" className="ghost-button" onClick={() => onRemove(placement.id)} title="Удалить посадку (Delete)">
            <Trash2 size={15} />
            Удалить
          </button>
        )}
      </div>

      {error ? (
        <p className="verdict tone-stop">{error}</p>
      ) : !check && loading ? (
        <p className="verdict">Проверяем…</p>
      ) : (
        <p className={`verdict tone-${verdict.tone}`}>{verdict.text}</p>
      )}

      {near.length > 0 && (
        <ul className={`check-list ${loading ? "is-stale" : ""}`}>
          {near.map((c) => (
            <CheckRow key={c.rule_id} check={c} rule={rulesById[c.rule_id]} />
          ))}
        </ul>
      )}

      {far.length > 0 && (
        <p className="muted small absent-line">
          Дальше {FAR_M} м: {far.map((c) => lowerFirst(rulesById[c.rule_id].object_label)).filter((v, i, all) => all.indexOf(v) === i).join(", ")}.
        </p>
      )}

      {absent.length > 0 && (
        <p className="muted small absent-line">
          Нет в чертеже: {absent.map((c) => lowerFirst(rulesById[c.rule_id].object_label)).join(", ")}.
        </p>
      )}

      {check && (
        <p className="muted small">
          Нормы для: {PLANTING_LABEL[placement.species_type]}. Расстояния — от центра посадки до ближайшей точки объекта.
        </p>
      )}
    </div>
  );
}
