import { type Plan } from "./state";
import { CharacterName } from "../../ui/CharacterName";
import { ConfidencePill } from "../../ui/ConfidencePill";
import { ItemLink } from "../../ui/ItemLink";
import { Money } from "../../ui/Money";
import { EvidenceTip } from "../../ui/Evidence";
import { SkillBand } from "../../ui/SkillBand";
import { Pill, Tip } from "../../ui/parts";
import { SignalPill } from "../../ui/SignalPill";
import { PlanText } from "./PlanText";
import styles from "../../ui/components.module.css";
type Line = Plan["stops"][number]["lines"][number];
type QueueLine = {
  stage?: string;
  vendor_instead?: boolean;
  name?: string;
  units?: number;
  quantity?: number;
  purchased_units?: number;
  batch_size?: number;
  confidence?: string;
  confidence_reasons?: string[];
  highest_unit_copper?: number;
  cost_copper?: number;
  unit_copper?: number | null;
  profit_copper?: number | null;
  deposit_copper?: number | null;
  held_outputs?: { units: number; character: string; kind: string }[];
};
export function Warnings({ text }: { text?: string }) {
  if (!text) return null;
  return (
    <>
      {text.split("; ").map((s, i) => (
        <Tip key={i} text={s}>
          {s.startsWith("contested") ? (
            <SignalPill label="contested" />
          ) : (
            <Pill tone="warn">
              {s.startsWith("priced at") ? "typical price" : s}
            </Pill>
          )}
        </Tip>
      ))}
    </>
  );
}

function LineMoney({ row }: { row: QueueLine }) {
  if (row.stage === "auction house" || row.stage === "vendor")
    return (
      <>
        <Money copper={row.highest_unit_copper ?? null} /> / unit ·{" "}
        <Money copper={row.cost_copper ?? null} /> total
      </>
    );
  if (row.stage === "post")
    return (
      <>
        <Money copper={row.unit_copper ?? null} /> / unit ·{" "}
        <Money copper={row.profit_copper ?? null} /> profit
        <br />
        {row.vendor_instead ? (
          <span>Deposits excluded: refunded on an auction sale</span>
        ) : (
          <>
            Deposit <Money copper={row.deposit_copper ?? null} /> · back on sale
          </>
        )}
      </>
    );
  return null;
}
function RouteLine({
  line,
  data,
  tick,
}: {
  line: Line;
  data: Plan;
  tick: (index: number, checked: boolean) => void;
}) {
  const row = line.evidence as QueueLine;
  const display = line.display || {};
  const item = typeof display.item_id === "number" ? display.item_id : null;
  const band =
    typeof display.skillup_band === "string" ? display.skillup_band : "";
  const actionNote =
    typeof display.action_note === "string" ? display.action_note : "";
  const verb = row.vendor_instead
    ? "Vendor it instead"
    : row.stage === "craft"
      ? "Craft"
      : row.stage === "post"
        ? "Post"
        : row.stage === "take"
          ? "Take"
          : row.stage === "mail"
            ? "Mail"
            : "Buy";
  return (
    <div className={styles.step}>
      <input
        type="checkbox"
        aria-label={line.text}
        checked={!!data.state.ticks?.[String(line.index)]}
        onChange={(e) => tick(line.index, e.target.checked)}
      />
      <div className={styles["step-what"]}>
        {item && row.name ? (
          <>
            <span>
              {verb}{" "}
              {row.purchased_units ??
                row.batch_size ??
                row.units ??
                row.quantity}{" "}
              ×
            </span>{" "}
            <ItemLink
              id={item}
              name={row.name}
              quality={
                typeof display.quality === "number" ? display.quality : null
              }
            />
            {row.stage === "post" &&
              row.held_outputs?.map((held, i) => (
                <span key={i}>
                  + {held.units} held ({held.character}, {held.kind})
                </span>
              ))}
            {row.stage === "mail" ? (
              <span>
                to {String(line.evidence.to)}
                {actionNote}
              </span>
            ) : (
              actionNote && <span>{actionNote}</span>
            )}
          </>
        ) : (
          <PlanText text={line.text} characters={data.characters} />
        )}
        {band && <SkillBand text={band} />}
        {row.confidence && (
          <ConfidencePill
            level={row.confidence}
            reasons={row.confidence_reasons || []}
          />
        )}
        <Warnings text={line.warnings} />
      </div>
      <div className={styles["step-meta"]}>
        <LineMoney row={row} />{" "}
        <EvidenceTip
          label="Line"
          iconOnly
          data={{ ...line.evidence, ...display, queue_text: line.text }}
        />
      </div>
    </div>
  );
}
export function Route({
  data,
  tick,
}: {
  data: Plan;
  tick: (index: number, checked: boolean) => void;
}) {
  return (
    <div className={styles["compact-route"]}>
      {!data.stops.length && (
        <p>
          {data.empty_reason ||
            "No funded crafts. Open settings or inspect the plan evidence."}
        </p>
      )}
      {data.stops.map((stop, i) => (
        <div key={i} className={styles.stop}>
          <span className={styles["stop-n"]}>{i + 1}</span>
          <span className={styles["stop-line"]} />
          <div className={styles["stop-body"]}>
            <div className={styles["stop-title"]}>
              {stop.characters.length
                ? stop.characters.map((c) => (
                    <CharacterName character={c} key={c.join("|")} />
                  ))
                : stop.character}
              <span> · {stop.place}</span>
            </div>
            {stop.place === "mailbox" && (
              <small>{data.plan.queue.mail_note}</small>
            )}
            <div className={styles.steps}>
              {stop.lines.map((line) => (
                <RouteLine
                  key={line.index}
                  line={line}
                  data={data}
                  tick={tick}
                />
              ))}
            </div>
          </div>
        </div>
      ))}
      <details>
        <summary>Queue text and totals</summary>
        <pre style={{ whiteSpace: "pre-wrap" }}>{data.copy_text}</pre>
      </details>
    </div>
  );
}
