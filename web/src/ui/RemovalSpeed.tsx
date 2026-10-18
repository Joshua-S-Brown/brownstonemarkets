import styles from "./components.module.css";
import type { components } from "../api/schema";

export function RemovalSpeed({
  speed,
  suggested = false,
}: {
  speed: components["schemas"]["Speed"] | null | undefined;
  suggested?: boolean;
}) {
  if (!speed) return <span>Removal evidence unavailable</span>;
  return (
    <div className={styles.removalSpeed}>
      <p>{speed.label}</p>
      <p>
        {speed.daily_units === null ? (
          speed.reason
        ) : (
          <>
            {speed.daily_units.toLocaleString()} units/day · {speed.pairs} scan
            gaps, {speed.hours.toFixed(1)} hours
          </>
        )}
      </p>
      {speed.daily_units !== null && (
        <p>
          {speed.days_supply === null
            ? speed.reason
            : `≈ ${speed.days_supply.toFixed(1)} days of listed supply`}
        </p>
      )}
      {suggested && <p>Suggested: {speed.suggested_units?.toLocaleString() ?? "—"} units</p>}
      <details>
        <summary>Removal rate evidence</summary>
        <p>
          Window {speed.settings.speed_window_days} days · minimum{" "}
          {speed.settings.speed_min_pairs} gaps /{" "}
          {speed.settings.speed_min_hours} hours
        </p>
        <p>
          Median listed: {speed.median_units ?? "unknown"} units · cover{" "}
          {speed.settings.speed_cover_days} days · cap{" "}
          {speed.settings.speed_cap_percent}%
        </p>
        <p>
          Could have expired and time left unknown are excluded. Gaps with this
          identity absent earlier are excluded.
        </p>
      </details>
    </div>
  );
}
