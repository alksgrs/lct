import {
  CheckCircle2,
  MapPin,
  X
} from "lucide-react";

import type { Placement } from "../types/api";

const typeLabel = (
  type: Placement["species_type"]
) =>
  type === "tree"
    ? "Дерево"
    : type === "shrub"
      ? "Кустарник"
      : "Покрытие";

export default function PlacementDetails({
  placement,
  onClose
}: {
  placement: Placement;
  onClose: () => void;
}) {
  return (
    <div
      className="details-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={`Обоснование посадки №${placement.id}`}
    >
      <button
        className="details-backdrop"
        type="button"
        onClick={onClose}
        aria-label="Закрыть"
      />

      <section className="details-drawer">
        <div className="details-header">
          <div>
            <span className="eyebrow">
              Объяснение результата
            </span>

            <h3>
              {typeLabel(placement.species_type)}{" "}
              №{placement.id}
            </h3>
          </div>

          <button
            className="icon-button"
            type="button"
            onClick={onClose}
            aria-label="Закрыть"
          >
            <X size={19} />
          </button>
        </div>

        <div className="coordinates">
          <MapPin size={14} />

          X: {placement.x.toFixed(2)}
          {" · "}
          Y: {placement.y.toFixed(2)}
        </div>

        <div className="detail-status">
          <CheckCircle2 size={17} />
          Посадка допустима
        </div>

        <h4>Нормативное обоснование</h4>

        {placement.rationale.length > 0 ? (
          placement.rationale.map((rule) => (
            <div
              className="rule-box"
              key={rule.id}
            >
              <strong>
                {rule.source}
              </strong>

              <span>
                Пункт: {rule.clause}
              </span>

              {rule.min_distance_m > 0 && (
                <span>
                  Минимальный отступ:{" "}
                  {rule.min_distance_m} м
                </span>
              )}

              <small>
                {rule.verified
                  ? "✓ Источник отмечен как проверенный"
                  : "⚠ Источник требует проверки"}
              </small>
            </div>
          ))
        ) : (
          <div className="detail-muted">
            Для этой посадки нормативное обоснование
            не передано сервером.
          </div>
        )}
      </section>
    </div>
  );
}
