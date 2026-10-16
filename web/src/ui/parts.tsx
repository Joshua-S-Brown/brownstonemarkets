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
export function Tip({
  text,
  children,
  onClick,
}: {
  text: string;
  children: ReactNode;
  onClick?: () => void;
}) {
  return (
    <Tooltip.Provider>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <button className={styles["tip"]} onClick={onClick}>
            {children}
          </button>
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
      <a href={"/app/today?" + new URLSearchParams({ sheet: "data", source })}>
        Open Data
      </a>
    </section>
  );
}
export function Sparkline({
  values,
  label,
}: {
  values: (number | null)[];
  label: string;
}) {
  const priced = values.filter((v): v is number => v !== null);
  if (priced.length < 2) return <span>{label}: not enough history</span>;
  const min = Math.min(...priced),
    range = Math.max(...priced) - min || 1;
  return (
    <svg
      viewBox="0 0 100 28"
      width="100"
      height="28"
      role="img"
      aria-label={label}
    >
      {values.map((v, i) =>
        v !== null && i > 0 && values[i - 1] !== null ? (
          <line
            key={i}
            stroke="currentColor"
            x1={((i - 1) * 100) / Math.max(values.length - 1, 1)}
            y1={26 - ((values[i - 1]! - min) * 24) / range}
            x2={(i * 100) / Math.max(values.length - 1, 1)}
            y2={26 - ((v - min) * 24) / range}
          />
        ) : null,
      )}
    </svg>
  );
}
