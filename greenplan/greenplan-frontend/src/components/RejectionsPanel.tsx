import { ChevronDown, Crosshair } from "lucide-react";
import { useMemo, useState } from "react";

import { PLANTING_LABEL, count, meters, num, ruleNorm } from "../format";
import type { Rejection, Rule } from "../types";

interface Props {
  rejections: Rejection[];
  rulesById: Record<string, Rule>;
  activeRule: string | null;
  onShowRule: (ruleId: string | null) => void;
  onFocus: (x: number, y: number) => void;
}

interface Group {
  rule: Rule;
  items: Rejection[];
  medianShortfall: number | null;
}

const LIST_LIMIT = 60;

function median(values: number[]): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

export default function RejectionsPanel({ rejections, rulesById, activeRule, onShowRule, onFocus }: Props) {
  const [open, setOpen] = useState<string | null>(null);

  const groups = useMemo(() => {
    const map = new Map<string, Rejection[]>();
    for (const item of rejections) {
      const list = map.get(item.rule_id);
      if (list) list.push(item);
      else map.set(item.rule_id, [item]);
    }
    const result: Group[] = [];
    for (const [ruleId, items] of map) {
      const rule = rulesById[ruleId];
      if (!rule) continue;
      result.push({
        rule,
        items,
        medianShortfall: median(items.map((i) => i.shortfall_m).filter((v): v is number => v !== null)),
      });
    }
    return result.sort((a, b) => b.items.length - a.items.length);
  }, [rejections, rulesById]);

  if (rejections.length === 0) {
    return (
      <div className="panel-body">
        <div className="empty">
          <p>Отклонённых точек нет.</p>
          <p className="muted">Все узлы сетки внутри участка прошли проверку норм.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="panel-body">
      <div className="lede">
        <p>
          Узлы сетки размещения, которые не прошли проверку: {count(rejections.length, ["точка", "точки", "точек"])}. В DXF они не
          попадают. Здесь видно, какая норма чаще всего ограничивает посадку.
        </p>
      </div>
      <ul className="reject-groups">
        {groups.map((group) => {
          const id = group.rule.rule_id;
          const expanded = open === id;
          const shown = activeRule === id;
          return (
            <li key={id} className={`reject-group ${shown ? "active" : ""}`}>
              <div className="reject-head">
                <button type="button" className="reject-title" onClick={() => setOpen(expanded ? null : id)} aria-expanded={expanded}>
                  <ChevronDown size={14} className={`chevron ${expanded ? "open" : ""}`} />
                  <span>
                    {group.rule.object_label}
                    <span className="norm-planting">{PLANTING_LABEL[group.rule.planting]}</span>
                  </span>
                </button>
                <span className="reject-count mono">{num(group.items.length)}</span>
                <button
                  type="button"
                  className={`chip-button ${shown ? "active" : ""}`}
                  onClick={() => onShowRule(shown ? null : id)}
                >
                  {shown ? "скрыть" : "на плане"}
                </button>
              </div>
              <p className="reject-meta muted small">
                {ruleNorm(group.rule)}
                {group.medianShortfall !== null && group.rule.kind === "distance" && <> · обычно не хватает {meters(group.medianShortfall)}</>}
              </p>
              {expanded && (
                <ol className="reject-items">
                  {group.items.slice(0, LIST_LIMIT).map((item) => (
                    <li key={item.id}>
                      <span className="mono">{item.distance_m === null ? "—" : meters(item.distance_m)}</span>
                      <span className="muted small">{item.species_type === "tree" ? "дерево" : "кустарник"}</span>
                      <button type="button" className="icon-button" title="Показать на плане" onClick={() => onFocus(item.x, item.y)}>
                        <Crosshair size={14} />
                      </button>
                    </li>
                  ))}
                  {group.items.length > LIST_LIMIT && (
                    <li className="muted small">и ещё {num(group.items.length - LIST_LIMIT)}</li>
                  )}
                </ol>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
