import { useQuery } from "@tanstack/react-query";
import { get } from "../../api/client";
import { type Plan } from "./state";
import { ItemLink } from "../../ui/ItemLink";
import { CharacterName } from "../../ui/CharacterName";
import { Money } from "../../ui/Money";
import { ConfidencePill } from "../../ui/ConfidencePill";
import { EvidenceTip } from "../../ui/Evidence";
import { Sparkline } from "../../ui/parts";
import { PlanText } from "./PlanText";
import { Warnings } from "./Route";
import styles from "../../ui/components.module.css";
export type Unplanned = {
  catalog_id: string;
  recipe_id: number;
  output_item_id: number;
  output_name: string;
  profession: string;
  required_skill?: number | null;
  tonight_reason: string;
  profit_copper: number | null;
};
function History({ source, item }: { source: string; item: number }) {
  const query = useQuery({
    queryKey: [source, "history", item],
    queryFn: ({ signal }) =>
      get<{ points: { metrics: { min_buyout?: number | null } | null }[] }>(
        `items/${item}/history`,
        source,
        signal,
      ),
    staleTime: Infinity,
  });
  const values =
    query.data?.points?.map((p) => p.metrics?.min_buyout ?? null) || [];
  return values.filter((v) => v !== null).length >= 2 ? (
    <Sparkline values={values} label="Stored lowest unit buyout" />
  ) : null;
}
export function reasonText(row: Unplanned) {
  if (row.tonight_reason === "rank below required skill")
    return `needs ${row.profession.charAt(0).toUpperCase()}${row.profession.slice(1)} ${row.required_skill ?? "(rank unknown)"}`;
  if (row.tonight_reason === "needs pattern or other source")
    return "pattern not learned";
  return row.tonight_reason;
}
export function bestLever(session: Plan["session"]) {
  const characters = (session?.characters || []) as {
    character: [string, string, string];
    options_text: string[];
    next_steps?: { kind: string }[];
  }[];
  for (const c of characters) {
    const index =
      c.next_steps?.findIndex((s) => s.kind === "level_profession") ??
      c.options_text.findIndex(
        (s) => s.startsWith("Level ") && s.includes("unlocks"),
      );
    if (index >= 0)
      return { character: c.character, text: c.options_text[index] };
  }
  return null;
}
export function Opportunities({
  data,
  source,
  session,
  openLevel,
  hideLow,
}: {
  data: Plan;
  source: string;
  session?: Plan["session"];
  openLevel: () => void;
  hideLow: (value: boolean) => void;
}) {
  const lever = bestLever(session);
  return (
    <>
      {lever && (
        <section className={styles.lever} aria-label="Biggest lever">
          <div>
            <strong>Biggest lever</strong>{" "}
            <CharacterName character={lever.character} />
            <p>
              <PlanText text={lever.text} characters={[lever.character]} />
            </p>
            <small>Your own past sessions, not a promise.</small>
            <br />
            <button onClick={openLevel}>Open Level up</button>
          </div>
        </section>
      )}
      <label>
        <input
          type="checkbox"
          checked={!!data.state.hide_low}
          onChange={(e) => hideLow(e.target.checked)}
        />{" "}
        Hide Low confidence
      </label>
      <details>
        <summary>Choices and visibility</summary>
        <p>
          {data.state.hide_low
            ? data.plan.craft.filter((r) => r.confidence === "Low").length
            : 0}{" "}
          Low confidence crafts hidden; the complete Route is retained.
        </p>
        <p>
          Open an item’s Our move panel to adjust its batch, choice, or refill.
        </p>
      </details>
      {data.plan.craft
        .filter((row) => !data.state.hide_low || row.confidence !== "Low")
        .map((row) => (
          <div className={styles.opp} key={row.catalog_id + row.recipe_id}>
            <ItemLink id={row.output_item_id} name={row.output_name} />
            <span className={styles.big}>
              <Money copper={row.headline_per_craft_copper} />
            </span>
            <div className={styles.why}>
              Planned · {row.batch_size} crafts ·{" "}
              <PlanText
                text={row.made_by || "Maker unknown"}
                characters={data.characters}
              />{" "}
              · per craft {row.profit_basis}
              <ConfidencePill
                level={row.confidence}
                reasons={row.confidence_reasons}
              />
              <Warnings text={row.warnings_text} />
              <History source={source} item={row.output_item_id} />
              <EvidenceTip label="Opportunity evidence" data={row} />
            </div>
          </div>
        ))}
      {(data.plan.unplanned || []).slice(0, 5).map((row) => (
        <div className={styles.opp} key={row.catalog_id + row.recipe_id}>
          <ItemLink id={row.output_item_id} name={row.output_name} />
          <span className={styles.big}>
            <Money copper={row.profit_copper} />
          </span>
          <div className={styles.why}>
            {reasonText(row)} · per craft at cautious sale price
            <History source={source} item={row.output_item_id} />
            <EvidenceTip label="Opportunity evidence" data={row} />
          </div>
        </div>
      ))}
    </>
  );
}
