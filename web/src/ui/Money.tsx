import styles from "../theme/app.module.css";
export function moneyText(copper: number | null): string {
  if (copper === null) return "—";
  const value = Math.abs(copper),
    gold = Math.floor(value / 10000),
    silver = Math.floor((value % 10000) / 100),
    coins = value % 100;
  const parts = gold ? [gold.toLocaleString("en-US") + "g"] : [];
  if (silver) parts.push(silver + "s");
  if (coins || !parts.length) parts.push(coins + "c");
  return (copper < 0 ? "-" : "") + parts.join(" ");
}
export function Money({ copper }: { copper: number | null }) {
  return (
    <span className={`${styles.money} ${copper === 0 ? styles.muted : ""}`}>
      {moneyText(copper)
        .split(" ")
        .map((part, i) => (
          <span key={i} className={styles["coin-" + part.slice(-1)]}>
            {i > 0 ? " " : ""}
            {part}
          </span>
        ))}
    </span>
  );
}
