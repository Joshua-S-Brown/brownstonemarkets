import { useState } from "react";
import styles from "../../theme/app.module.css";
import { Evidence } from "../../ui/Evidence";
import { Pill } from "../../ui/parts";
import { post } from "../../api/client";
import type { components } from "../../api/schema";
export type Reviewed = components["schemas"]["Review"];
export function Review({
  source,
  data,
  busy,
  collect,
}: {
  source: string;
  data: Reviewed;
  busy: boolean;
  collect: (selected: string[]) => void;
}) {
  const [review, setReview] = useState(data.review!);
  const [changing, setChanging] = useState(false),
    [error, setError] = useState("");
  async function select(selected: string[]) {
    setChanging(true);
    setError("");
    try {
      setReview(
        await post<components["schemas"]["Selection"]>(
          "data/selection",
          source,
          { review_id: data.review_id, selected },
        ),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setChanging(false);
    }
  }
  return (
    <>
      <Pill tone={review.new ? "warn" : "good"}>
        {review.new ? "New" : "Up to date"}
      </Pill>
      <h2>
        {review.new ? "New evidence waiting" : "Nothing new for this source"}
      </h2>
      {review.lines.map((s, i) => (
        <p key={i}>{s}</p>
      ))}
      {review.problems.map((s, i) => (
        <p role="status" key={i}>
          {s}
        </p>
      ))}
      {error && <p role="alert">{error}</p>}
      {review.can_import && (
        <button
          className={styles["primary"]}
          disabled={busy || changing}
          onClick={() => collect(review.selected)}
        >
          Import
        </button>
      )}
      {review.file_status.map((s, i) => (
        <p key={i}>{s}</p>
      ))}
      {review.clear.map((s, i) => (
        <Pill key={i}>{s}</Pill>
      ))}
      <details open={review.problems.length > 0 || undefined}>
        <summary>Details</summary>
        <Evidence data={{ sections: review.sections, notes: review.notes }} />
        {review.choices.map((choice) => (
          <label key={choice}>
            <input
              type="checkbox"
              disabled={changing || busy}
              checked={review.selected.includes(choice)}
              onChange={(e) =>
                void select(
                  e.target.checked
                    ? [...review.selected, choice]
                    : review.selected.filter((s) => s !== choice),
                )
              }
            />
            {choice}
          </label>
        ))}
      </details>
    </>
  );
}
