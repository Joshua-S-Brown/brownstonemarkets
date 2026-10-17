import styles from "./signals.module.css";
export const signalLabels = [
  "steady",
  "contested",
  "cheap",
  "high",
  "thin",
  "removed early",
] as const;
export function isSignal(
  value: string,
): value is (typeof signalLabels)[number] {
  return (signalLabels as readonly string[]).includes(value);
}
export function SignalPill({
  label,
}: {
  label: "steady" | "contested" | "cheap" | "high" | "thin" | "removed early";
}) {
  return (
    <span className={styles.pill} data-signal={label}>
      {label}
    </span>
  );
}
