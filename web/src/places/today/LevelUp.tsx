import { CharacterName } from "../../ui/CharacterName";
import { PlanText } from "./PlanText";
import { Evidence } from "../../ui/Evidence";
import { Money } from "../../ui/Money";
import { ItemLink } from "../../ui/ItemLink";
import { type CharacterKey } from "../../app/InspectorContext";
import type { Plan } from "./state";
import styles from "../../theme/app.module.css";
type Recipe = {
  output_item_id: number;
  name: string;
  profit_copper: number | null;
  board_reason: string;
  skillup_band: string;
  required_skill: number;
  estimate: {
    complete: boolean;
    cost_copper: number | null;
    reasons: string[];
  };
};
type Estimate = Recipe["estimate"];
type Group = {
  profession: string;
  rank: number | null;
  max_rank: number | null;
  recipes: Recipe[];
  milestones: { skill: number; estimate: Estimate; recipes: Recipe[] }[];
  tier: object | null;
  capped: boolean;
};
type FarmRow = {
  item_id: number;
  item_name?: string;
  units_per_hour: number;
  value_per_hour_copper: number | null;
  typical_price_copper?: number | null;
  zone: string;
  source_kind: string;
  seconds: number;
};
type Spot = {
  npc_id: number | null;
  mob: string;
  zone: string;
  position: string;
  value_per_hour_copper: number | null;
  seconds: number;
  stretches: number;
  coin_share: string;
  no_price_items: number;
  no_price_units: number;
};
type Character = {
  character: CharacterKey;
  options_text: string[];
  professions: Group[];
  crafts: object[];
  level: number | null;
  farming: {
    rows: FarmRow[];
    spots: Spot[];
    recorded_seconds: number;
    excluded_stretches: number;
  };
};
export function LevelUp({
  session,
}: {
  session: NonNullable<Plan["session"]>;
}) {
  const characters = (session.characters || []) as Character[];
  return (
    <>
      <h2>This session</h2>
      <p>
        Your own past sessions, not a promise; launch respawn competition
        differs; listings are not sales.
      </p>
      {!characters.length && (
        <p>
          No scoped Today characters imported. Open each profession window next
          login.
        </p>
      )}
      {characters.map((c) => (
        <section key={c.character.join("|")} className={styles["route-stop"]}>
          <h2>
            <CharacterName character={c.character} /> · level{" "}
            {c.level ?? "unknown"}
          </h2>
          {c.options_text.map((s, i) => (
            <p key={i}>
              → <PlanText text={s} characters={[c.character]} />
            </p>
          ))}
          {c.professions.map((g) => (
            <section key={g.profession}>
              <h3>
                {g.profession} · {g.rank ?? "unknown"} /{" "}
                {g.max_rank ?? "unknown"}
              </h3>
              {g.capped && <p>Capped · train the next tier first.</p>}
              {g.milestones.map((m) => (
                <section key={m.skill}>
                  <h4>
                    Reach {m.skill} · cost{" "}
                    {m.estimate.complete ? (
                      <Money copper={m.estimate.cost_copper} />
                    ) : (
                      <>
                        unknown ·{" "}
                        <PlanText text={m.estimate.reasons.join("; ")} />
                      </>
                    )}
                  </h4>
                  {m.recipes.map((r) => (
                    <div key={r.output_item_id}>
                      <ItemLink id={r.output_item_id} name={r.name} />
                      <p>
                        {r.skillup_band} · profit per craft{" "}
                        {r.profit_copper === null ? (
                          <>unknown · {r.board_reason}</>
                        ) : (
                          <Money copper={r.profit_copper} />
                        )}
                      </p>
                      <details>
                        <summary>Cost and confidence evidence</summary>
                        <Evidence data={r} />
                      </details>
                    </div>
                  ))}
                </section>
              ))}
              <details>
                <summary>Tier steps and profession evidence</summary>
                <Evidence data={g} />
              </details>
            </section>
          ))}
          <h3>Farming</h3>
          {!c.farming.rows.length && (
            <p>
              Not enough farming history ·{" "}
              {(c.farming.recorded_seconds / 60).toFixed(1)} minutes recorded.
            </p>
          )}
          {c.farming.rows.slice(0, 3).map((r, i) => (
            <p key={i}>
              <ItemLink
                id={r.item_id}
                name={r.item_name || `Item ${r.item_id}`}
              />{" "}
              · {r.zone} · {r.source_kind} · {r.units_per_hour} units/hour ·{" "}
              {r.value_per_hour_copper === null ? (
                "no price"
              ) : (
                <Money copper={r.value_per_hour_copper} />
              )}{" "}
              per hour · typical unit{" "}
              <Money copper={r.typical_price_copper ?? null} /> ·{" "}
              {(r.seconds / 60).toFixed(1)} evidence minutes
            </p>
          ))}
          {!!c.farming.spots.length && <h3>Farming spots</h3>}
          {c.farming.spots.map((s, i) => (
            <div key={i}>
              <p>
                {s.zone} ·{" "}
                {s.npc_id ? (
                  <a href={`https://www.wowhead.com/classic/npc=${s.npc_id}`}>
                    {s.mob}
                  </a>
                ) : (
                  "zone-only gathering"
                )}{" "}
                · {s.position} ·{" "}
                {s.value_per_hour_copper === null ? (
                  "no price"
                ) : (
                  <Money copper={s.value_per_hour_copper} />
                )}{" "}
                per hour · {(s.seconds / 60).toFixed(1)} minutes · {s.stretches}{" "}
                stretches · {s.coin_share} · {s.no_price_items} items /{" "}
                {s.no_price_units} units unpriced
              </p>
              <details>
                <summary>Spot item values</summary>
                <Evidence data={s} />
              </details>
            </div>
          ))}
          <details>
            <summary>
              Farming evidence · {c.farming.excluded_stretches} skipped
              stretches
            </summary>
            <Evidence data={c.farming} />
          </details>
          <details>
            <summary>Reserved crafts</summary>
            <Evidence data={{ crafts: c.crafts }} />
          </details>
        </section>
      ))}
      <details>
        <summary>How these options were made</summary>
        <Evidence
          data={{
            tier_explanation: session.tier_explanation,
            snapshot: session.snapshot,
            freshness: session.freshness,
          }}
        />
      </details>
    </>
  );
}
