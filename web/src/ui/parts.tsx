import styles from "../theme/app.module.css";
import type { ReactNode } from "react";
import * as Tooltip from "@radix-ui/react-tooltip";
export function Pill({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "good" | "warn" | "bad";
}) {
  return (
    <span className={styles["pill"]} data-tone={tone}>
      {children}
    </span>
  );
}
export function Tip({ text, children }: { text: string; children: ReactNode }) {
  return (
    <Tooltip.Provider>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <button className={styles["tip"]}>{children}</button>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content className={styles["popover"]} sideOffset={8}>
            {text}
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  );
}
export function EmptyState({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className={styles["empty"]}>
      <h2>{title}</h2>
      <div>{children}</div>
    </section>
  );
}
export function ErrorState({
  error,
  retry,
  source = "",
}: {
  source?: string;
  error: Error;
  retry: () => void;
}) {
  return (
    <section role="alert" className={styles["empty"]}>
      <h2>Saved evidence could not load</h2>
      <p>{error.message}</p>
      <button onClick={retry}>Retry</button>{" "}
      <a href={"/?" + new URLSearchParams({ place: "Data", source })}>
        Open Data
      </a>
    </section>
  );
}
export function Sparkline({
  values,
  label,
}: {
  values: number[];
  label: string;
}) {
  if (values.length < 2) return <span>{label}: not enough history</span>;
  const min = Math.min(...values),
    range = Math.max(...values) - min || 1;
  return (
    <svg
      viewBox="0 0 100 28"
      width="100"
      height="28"
      role="img"
      aria-label={label}
    >
      <polyline
        fill="none"
        stroke="currentColor"
        points={values
          .map(
            (v, i) =>
              `${(i * 100) / Math.max(values.length - 1, 1)},${26 - ((v - min) * 24) / range}`,
          )
          .join(" ")}
      />
    </svg>
  );
}
