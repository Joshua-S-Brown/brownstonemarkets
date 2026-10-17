import kit from "./components.module.css";
import { useInspector } from "../app/InspectorContext";
export function ItemLink({
  id,
  name,
  quality = null,
  variant,
  badge = false,
}: {
  id: number;
  name: string;
  quality?: number | null;
  variant?: string;
  badge?: boolean;
}) {
  const inspect = useInspector();
  const words = name.trim().split(/\s+/);
  const initials = (
    words.length > 1
      ? words
          .map((w) => w[0])
          .join("")
          .slice(0, 2)
      : name.trim().slice(0, 2)
  ).toUpperCase();
  return (
    <button
      className={kit.item}
      title={name}
      style={
        quality !== null && quality >= 0 && quality <= 8
          ? { color: `var(--q-${quality})` }
          : undefined
      }
      onClick={() => inspect(variant ? { item: id, variant } : { item: id })}
    >
      {badge && (
        <span className={kit.ic} aria-hidden="true">
          {initials}
        </span>
      )}
      <span className={kit.nm}>{name}</span>
    </button>
  );
}
