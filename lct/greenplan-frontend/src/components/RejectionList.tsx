import type { Rejection } from "../types/api";

const typeLabel = (
  type: Rejection["species_type"]
) =>
  type === "tree"
    ? "Дерево"
    : type === "shrub"
      ? "Кустарник"
      : "Покрытие";

export default function RejectionList({
  items
}: {
  items: Rejection[];
}) {
  if (!items.length) {
    return (
      <div className="empty-state">
        Отклонённых кандидатов нет.
      </div>
    );
  }

  return (
    <div className="rejection-list">
      {items.map((item) => (
        <article
          className="rejection-item"
          key={item.id}
        >
          <div className="rejection-title">
            <strong>
              Кандидат №{item.id}
            </strong>

            <span>
              {typeLabel(
                item.species_type
              )}
            </span>
          </div>

          <p>
            {item.reason}
          </p>

          <small>
            {item.violated.source.act}
            {" · "}
            {item.violated.source.clause}
          </small>
        </article>
      ))}
    </div>
  );
}