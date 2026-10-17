import { Pill, Tip } from "./parts";
export function ConfidencePill({
  level,
  reasons,
}: {
  level: string;
  reasons: string[];
}) {
  return (
    <Tip text={reasons.join("; ") || "No confidence reasons recorded"}>
      <Pill
        tone={
          level.toLowerCase() === "high"
            ? "good"
            : level.toLowerCase() === "medium"
              ? "warn"
              : "bad"
        }
      >
        {level}
      </Pill>
    </Tip>
  );
}
