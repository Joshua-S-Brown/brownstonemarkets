import type { ReactNode } from "react";
import { Evidence } from "./Evidence";
import styles from "./components.module.css";
export function Panel({
  title,
  subtitle,
  action,
  children,
  evidence,
}: {
  title: string;
  subtitle?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  evidence?: object;
}) {
  return (
    <section className={styles.panel}>
      <header className={styles["panel-h"]}>
        <h2>{title}</h2>
        <span className={styles.muted}>{subtitle}</span>
        <div className={styles.act}>{action}</div>
      </header>
      <div className={styles["panel-b"]}>{children}</div>
      {evidence && (
        <details className={styles.evidence}>
          <summary>Evidence</summary>
          <Evidence data={evidence} />
        </details>
      )}
    </section>
  );
}
