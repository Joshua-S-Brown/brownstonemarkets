import styles from "../theme/app.module.css";
import { useInspector } from "../app/InspectorContext";
export function ItemLink({
  id,
  name,
  quality = null,
}: {
  id: number;
  name: string;
  quality?: number | null;
}) {
  const inspect = useInspector();
  return (
    <button
      className={styles["item-link"]}
      style={
        quality !== null && quality >= 0 && quality <= 8
          ? { color: `var(--q-${quality})` }
          : undefined
      }
      onClick={() => inspect({ item: id })}
    >
      {name}
    </button>
  );
}
