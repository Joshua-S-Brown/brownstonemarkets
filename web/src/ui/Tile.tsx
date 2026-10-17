import type { ReactNode } from "react";
import styles from "./components.module.css";
export function Tile({
  label,
  value,
  caption,
  progress,
}: {
  label: string;
  value: ReactNode;
  caption?: ReactNode;
  progress?: number | null;
}) {
  return (
    <div className={styles.kpi}>
      <span className={styles.eyebrow}>{label}</span>
      <div className={styles.v}>{value}</div>
      <div className={styles.h}>{caption}</div>
      {progress != null && Number.isFinite(progress) && (
        <div
          className={styles.bar}
          role="progressbar"
          aria-label={label}
          aria-valuemin={0}
          aria-valuemax={1}
          aria-valuenow={Math.max(0, Math.min(1, progress))}
        >
          <i
            style={{ width: `${Math.max(0, Math.min(1, progress)) * 100}%` }}
          />
        </div>
      )}
    </div>
  );
}
