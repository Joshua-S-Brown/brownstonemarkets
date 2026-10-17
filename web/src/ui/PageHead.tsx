import type { ReactNode } from "react";
import styles from "./components.module.css";
export function PageHead({
  eyebrow,
  title,
  subtitle,
  action,
}: {
  eyebrow?: ReactNode;
  title: string;
  subtitle: string;
  action?: ReactNode;
}) {
  return (
    <header className={styles["page-head"]}>
      <div>
        <div className={styles.eyebrow}>{eyebrow}</div>
        <h1>{title}</h1>
        <div className={styles.sub}>{subtitle}</div>
      </div>
      <div className={styles.action}>{action}</div>
    </header>
  );
}
