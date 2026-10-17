import { Pill, Tip } from "./parts";
import styles from "./components.module.css";
export function SkillBand({ text }: { text: string }) {
  const colour = text.split(" ")[0];
  return (
    <Tip text={text}>
      <Pill>
        <span className={styles["skill-band"]} data-band={colour}>
          <i aria-hidden="true" />
          {text.startsWith("needs ")
            ? text.split(" · ").slice(0, 2).join(" · ")
            : text.startsWith("orange") ||
                text.startsWith("yellow") ||
                text.startsWith("green") ||
                text.startsWith("grey")
              ? colour
              : text.split(" · ")[0]}
        </span>
      </Pill>
    </Tip>
  );
}
