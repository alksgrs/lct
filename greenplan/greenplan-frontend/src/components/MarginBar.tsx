import { marginTone } from "../format";

export default function MarginBar({ distance, limit }: { distance: number | null; limit: number | null }) {
  if (distance === null || limit === null || limit <= 0) return <span className="margin-bar margin-bar-empty" />;
  const ratio = Math.min(distance / limit, 2) / 2;
  const tone = marginTone(distance - limit);
  return (
    <span className={`margin-bar tone-${tone}`} title={`${distance.toFixed(2)} м при норме ${limit} м`}>
      <span className="margin-bar-fill" style={{ width: `${ratio * 100}%` }} />
      <span className="margin-bar-norm" />
    </span>
  );
}
