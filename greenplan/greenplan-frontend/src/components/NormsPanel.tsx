import { ChevronDown } from "lucide-react";
import { useMemo, useState } from "react";

import { PLANTING_LABEL, area, count, lowerFirst, marginTone, meters, norm, num, ruleNorm } from "../format";
import type { Greening, PendingRule, Rule } from "../types";
import MarginBar from "./MarginBar";

interface Props {
  rules: Rule[];
  pending: PendingRule[];
  greening: Greening | null;
  activeRule: string | null;
  onShowRejections: (ruleId: string | null) => void;
}

function margin(rule: Rule): number | null {
  if (rule.closest_m === null || rule.closest_m === undefined || rule.limit_m === null) return null;
  return rule.closest_m - rule.limit_m;
}

function Source({ rule }: { rule: Rule }) {
  return (
    <div className="norm-source">
      <span>{rule.act}</span>
      <span>{rule.clause}</span>
      {rule.note && <span className="norm-note">{rule.note}</span>}
      {rule.source_url && (
        <a href={rule.source_url} target="_blank" rel="noreferrer">
          Текст акта
        </a>
      )}
      {rule.verified_by && (
        <span className="norm-verified">
          сверено: {rule.verified_by}
          {rule.verified_at ? `, ${rule.verified_at.split("-").reverse().join(".")}` : ""}
        </span>
      )}
    </div>
  );
}

function AppliedRow({ rule, active, onShowRejections }: { rule: Rule; active: boolean; onShowRejections: Props["onShowRejections"] }) {
  const [open, setOpen] = useState(false);
  const value = margin(rule);
  const tone = marginTone(value);
  return (
    <li className={`norm-row tone-${tone}`}>
      <button type="button" className="norm-head" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <span className="norm-title">
          {rule.object_label}
          <span className="norm-planting">{PLANTING_LABEL[rule.planting]}</span>
        </span>
        <span className="norm-limit">{ruleNorm(rule)}</span>
        <ChevronDown size={14} className={`chevron ${open ? "open" : ""}`} />
      </button>
      <div className="norm-fact">
        <MarginBar distance={rule.closest_m ?? null} limit={rule.limit_m} />
        <span className="norm-fact-text">
          {rule.closest_m === null || rule.closest_m === undefined ? (
            "посадок рядом нет"
          ) : (
            <>
              ближайшая {meters(rule.closest_m)}
              {value !== null && <span className="norm-margin"> · запас {num(value, 2)}</span>}
            </>
          )}
        </span>
        {(rule.rejected ?? 0) > 0 && (
          <button
            type="button"
            className={`chip-button ${active ? "active" : ""}`}
            onClick={() => onShowRejections(active ? null : rule.rule_id)}
            title="Показать отклонённые точки на плане"
          >
            {num(rule.rejected ?? 0)} откл.
          </button>
        )}
      </div>
      {open && <Source rule={rule} />}
    </li>
  );
}

const OFFSET_LABELS: Record<string, string> = {
  ROAD: "проезд",
  PAVEMENT: "тротуар, дорожка",
  BUILDING: "стена здания (отмостка)",
  MAF: "МАФ",
  TRAM_TRACK: "трамвайные пути",
  RETAINING_WALL: "подпорная стенка",
};

function GreeningSection({ greening, rules }: { greening: Greening; rules: Rule[] }) {
  const byId = new Map(rules.map((rule) => [rule.rule_id, rule]));
  const hedgeRules = greening.hedge_rule_ids
    .map((id) => byId.get(id))
    .filter((rule): rule is Rule => Boolean(rule) && rule!.state !== "not_applicable");
  const offsets = Object.entries(greening.lawn_offsets_m)
    .map(([kind, value]) => `${OFFSET_LABELS[kind] ?? kind} ${norm(value)}`)
    .join(", ");
  return (
    <>
      <h3 className="group-title">Газоны и элементы сквера</h3>
      <ul className="greening-list">
        <li>
          <span className="greening-head">
            <span className="swatch swatch-lawn" />
            Газоны
            <span className="mono">{area(greening.lawn_area_m2)}</span>
          </span>
          <span className="muted small">
            Табл. 3.6.1 расстояний для газонов не задаёт. Отступы от кромок проектные: {offsets}.
          </span>
        </li>
        <li>
          <span className="greening-head">
            <span className="swatch swatch-hedge" />
            Живые изгороди
            <span className="mono">
              {num(greening.hedges.length)} шт. · {num(greening.hedge_length_m)} м
            </span>
          </span>
          <span className="muted small">
            Ряды кустарника вдоль проездов и тротуаров. Проверены по всем нормам для кустарников
            {hedgeRules.length > 0 && <>: {hedgeRules.map((rule) => `${lowerFirst(rule.object_label)} ${ruleNorm(rule)}`).join("; ")}</>}.
            {greening.shrubs_replaced > 0 && (
              <> Изгороди и цветники заменили {count(greening.shrubs_replaced, ["отдельный кустарник", "отдельных кустарника", "отдельных кустарников"])}.</>
            )}
          </span>
        </li>
        <li>
          <span className="greening-head">
            <span className="swatch swatch-flower" />
            Цветники
            <span className="mono">{num(greening.flowerbeds.length)}</span>
          </span>
          <span className="muted small">
            Круглые клумбы в глубине крупных газонов, в стороне от деревьев и изгородей. Ставятся только там, где по нормам можно сажать кустарник, и не ближе 1 м от любых сетей — чтобы не перекапывать трассы.
          </span>
        </li>
      </ul>
    </>
  );
}

export default function NormsPanel({ rules, pending, greening, activeRule, onShowRejections }: Props) {
  const applied = useMemo(
    () =>
      rules
        .filter((rule) => rule.state === "applied")
        .sort((a, b) => (margin(a) ?? Infinity) - (margin(b) ?? Infinity)),
    [rules],
  );
  const notRegulated = rules.filter((rule) => rule.state === "not_regulated");
  const absent = rules.filter((rule) => rule.state === "not_applicable");
  const broken = applied.filter((rule) => (margin(rule) ?? 0) < -1e-6);
  const tightest = applied.find((rule) => margin(rule) !== null);

  return (
    <div className="panel-body">
      <div className="lede">
        {broken.length === 0 ? (
          <p>
            В плане нет посадок ближе нормы. Проверено {count(applied.length, ["норма", "нормы", "норм"])} по
            объектам, найденным в чертеже.
            {tightest && tightest.closest_m !== null && tightest.closest_m !== undefined && (
              <>
                {" "}
                Меньше всего запаса у нормы «{lowerFirst(tightest.object_label)}, {PLANTING_LABEL[tightest.planting]}»: {meters(tightest.closest_m)} при норме{" "}
                {meters(tightest.limit_m, 1)}.
              </>
            )}
          </p>
        ) : (
          <p className="lede-stop">
            Нарушено {count(broken.length, ["норма", "нормы", "норм"])}. Строки отмечены красным.
          </p>
        )}
      </div>

      <h3 className="group-title">Учтены в расчёте</h3>
      <ul className="norm-list">
        {applied.map((rule) => (
          <AppliedRow
            key={rule.rule_id}
            rule={rule}
            active={activeRule === rule.rule_id}
            onShowRejections={onShowRejections}
          />
        ))}
      </ul>

      {greening && <GreeningSection greening={greening} rules={rules} />}

      {notRegulated.length > 0 && (
        <>
          <h3 className="group-title">Расстояние не нормируется</h3>
          <ul className="plain-list">
            {notRegulated.map((rule) => (
              <li key={rule.rule_id}>
                <span>
                  {rule.object_label} — {PLANTING_LABEL[rule.planting]}
                </span>
                <span className="mono muted">{rule.closest_m !== null && rule.closest_m !== undefined ? meters(rule.closest_m) : "—"}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      {absent.length > 0 && (
        <>
          <h3 className="group-title">Объектов в чертеже нет</h3>
          <p className="muted small">
            Нормы загружены, но таких объектов на подоснове не найдено. Если они есть, проверьте типы слоёв.
          </p>
          <ul className="plain-list">
            {absent.map((rule) => (
              <li key={rule.rule_id}>
                <span>
                  {rule.object_label} — {PLANTING_LABEL[rule.planting]}
                </span>
                <span className="mono muted">{ruleNorm(rule)}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      {pending.length > 0 && (
        <>
          <h3 className="group-title">Ждут подтверждения, не применяются</h3>
          <ul className="plain-list">
            {pending.map((rule) => (
              <li key={rule.rule_id}>
                <span>
                  {rule.object_label} — {PLANTING_LABEL[rule.planting]}
                </span>
                <span className="mono muted">{ruleNorm(rule)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
