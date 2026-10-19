import { useEffect, useRef, useState } from "react";
import { Materials } from "../team/Path";
import { Panel } from "../../ui/Panel";
import { Pill, Tip } from "../../ui/parts";
import kit from "../../ui/components.module.css";
import { SkillBand } from "../../ui/SkillBand";
import { CharacterName } from "../../ui/CharacterName";
import { PlanText } from "./PlanText";
import { Evidence } from "../../ui/Evidence";
import { Money } from "../../ui/Money";
import { ItemLink } from "../../ui/ItemLink";
import { type CharacterKey } from "../../app/InspectorContext";
import type { Plan } from "./state";
import styles from "../../theme/app.module.css";
type Recipe = {
  recipe_id: number;
  catalog_id: string;
  points_needed: number;
  confidence: string;
  needs_pattern: boolean;
  skillup_colors?: number[] | null;
  output_item_id: number;
  name: string;
  profit_copper: number | null;
  board_reason: string;
  skillup_band: string;
  required_skill: number;
  estimate: {
    material_notes: string[];
    complete: boolean;
    cost_copper: number | null;
    reasons: string[];
    steps: { recipe: string }[];
  };
};
type Estimate = Recipe["estimate"];
type Group = {
  best: Recipe | null;
  note: string;
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
  next_steps: { kind: string; group?: Group }[];
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
  focusCard = false,
}: {
  session: NonNullable<Plan["session"]>;
  focusCard?: boolean;
}) {
  const characters = (session.characters || []) as Character[];
  const firstCard = useRef<HTMLElement>(null);
  useEffect(() => {
    if (focusCard) {
      firstCard.current?.scrollIntoView?.({ block: "start" });
      firstCard.current?.focus();
    }
  }, [focusCard]);
  let cardIndex = 0;
  return (
    <Panel
      title="Level up"
      subtitle="Your own past sessions, not a promise; launch respawn competition differs; listings are not sales."
    >
      {!characters.length && (
        <p>
          No scoped Today characters imported. Open each profession window next
          login.
        </p>
      )}
      <div className={kit["lvl-grid"]}>
        {characters.flatMap((c) =>
          (c.next_steps || [])
            .filter((s) => s.kind === "level_profession")
            .map((step, i) => {
              const g = c.professions.find(
                (g) => g.profession === step.group?.profession,
              )!;
              const best = g.best!;
              const row = g.recipes.find(
                (r) =>
                  r.catalog_id === best.catalog_id &&
                  r.recipe_id === best.recipe_id,
              );
              const colors = row?.skillup_colors;
              const start = Math.min(g.rank ?? 0, colors?.[0] ?? 0);
              const end = colors
                ? colors[3] + Math.max(1, colors[3] - colors[2])
                : 1;
              return (
                <section
                  key={c.character.join("|") + i}
                  ref={cardIndex++ === 0 ? firstCard : undefined}
                  tabIndex={-1}
                  aria-label={`${c.character[0]} ${g.profession}`}
                  className={kit["level-card"]}
                >
                  <header className={kit["panel-h"]}>
                    <div>
                      <CharacterName character={c.character} avatar />
                      <div className={kit.muted}>
                        {g.profession} {g.rank ?? "unknown"} /{" "}
                        {g.max_rank ?? "unknown"}
                      </div>
                    </div>
                    <Pill>about +{best.points_needed} skill</Pill>
                  </header>
                  <div className={kit["level-body"]}>
                    <div>
                      Reach {best.required_skill} to make{" "}
                      <ItemLink id={best.output_item_id} name={best.name} />
                    </div>
                    <div className={kit.muted}>
                      Levels on{" "}
                      {[
                        ...new Set(best.estimate.steps.map((s) => s.recipe)),
                      ].join(", ")}
                    </div>
                    <Tip text={row?.skillup_band || "skill-up range unknown"}>
                      {colors && g.rank !== null ? (
                        <>
                          <span
                            className={kit["level-band"]}
                            role="meter"
                            aria-label="Skill-up colour bands"
                            aria-valuemin={start}
                            aria-valuemax={end}
                            aria-valuenow={g.rank}
                          >
                            {colors[0] > start && (
                              <span style={{ flex: colors[0] - start }} />
                            )}
                            {colors.map((n, j) => (
                              <span
                                key={j}
                                style={{
                                  flex: (colors[j + 1] ?? end) - n,
                                  background: `var(--sk-${["orange", "yellow", "green", "grey"][j]})`,
                                }}
                              />
                            ))}
                            <i
                              style={{
                                left: `${(100 * (g.rank - start)) / (end - start)}%`,
                              }}
                            />
                          </span>
                          <span className={kit["level-scale"]}>
                            <span>{start}</span>
                            <span>you are at {g.rank}</span>
                            <span>{end}</span>
                          </span>
                        </>
                      ) : (
                        "skill-up range unknown"
                      )}
                    </Tip>
                    <dl className={kit.kv}>
                      <dt>Materials to reach</dt>
                      <dd>
                        {best.estimate.complete &&
                        best.estimate.cost_copper !== null ? (
                          <Money copper={best.estimate.cost_copper} />
                        ) : (
                          <>
                            unknown ·{" "}
                            <PlanText text={best.estimate.reasons.join("; ")} />
                          </>
                        )}
                      </dd>
                      <dt>Earns per craft</dt>
                      <dd>
                        {best.profit_copper === null ? (
                          "unknown"
                        ) : (
                          <>
                            {best.profit_copper > 0 && "+"}
                            <Money copper={best.profit_copper} />
                          </>
                        )}
                      </dd>
                    </dl>
                    <Materials estimate={best.estimate} />
                    <div className={kit.muted}>
                      {best.confidence} confidence
                      {best.needs_pattern && " · needs a pattern"}
                    </div>
                    <Tiers group={g} summary="All tiers and recipes" />
                  </div>
                </section>
              );
            }),
        )}
      </div>
      <h3>No levelling step</h3>
      <ul aria-label="No levelling step">
        {characters.flatMap((c) => {
          const groups = c.professions.filter(
            (g) =>
              !c.next_steps?.some(
                (s) =>
                  s.kind === "level_profession" &&
                  s.group?.profession === g.profession,
              ),
          );
          return (c.professions.length ? groups : [null]).map((g) => (
            <li key={c.character.join("|") + g?.profession}>
              <CharacterName character={c.character} /> ·{" "}
              {g?.profession || "no profession seen"} ·{" "}
              <PlanText
                text={
                  c.options_text.find(
                    (_, i) =>
                      c.next_steps?.[i]?.kind === "nothing" ||
                      c.next_steps?.[i]?.kind === "evidence",
                  ) ||
                  g?.best?.estimate.reasons.join("; ") ||
                  g?.note ||
                  c.options_text
                    .filter(
                      (_, i) =>
                        c.next_steps?.[i]?.group?.profession === g?.profession,
                    )
                    .join("; ") ||
                  c.options_text.join("; ")
                }
                characters={[c.character]}
              />
              {g && (
                <Tiers
                  group={g}
                  summary={`All tiers and recipes · ${g.profession}`}
                />
              )}
            </li>
          ));
        })}
      </ul>
      {characters.map((c) => (
        <section key={c.character.join("|")} className={styles["route-stop"]}>
          <h3>
            <CharacterName character={c.character} /> · Farming
          </h3>
          <details>
            <summary>Other session options</summary>
            {c.options_text
              .filter((_, i) => c.next_steps?.[i]?.kind !== "level_profession")
              .map((text, i) => (
                <p key={i}>
                  <PlanText text={text} characters={[c.character]} />
                </p>
              ))}
          </details>

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
    </Panel>
  );
}

function Tiers({ group: g, summary }: { group: Group; summary: string }) {
  const [open, setOpen] = useState(false);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  return (
    <details onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary>{summary}</summary>
      {open && (
        <>
          {g.capped && <p>Capped · train the next tier first.</p>}
          {g.milestones.map((m) => (
            <section key={m.skill}>
              <h4>
                Reach {m.skill} · cost{" "}
                {m.estimate.complete ? (
                  <Money copper={m.estimate.cost_copper} />
                ) : (
                  <>
                    unknown · <PlanText text={m.estimate.reasons.join("; ")} />
                  </>
                )}
              </h4>
              <Materials estimate={m.estimate} />
              <TierRecipes recipes={m.recipes} />
            </section>
          ))}
          <details
            onToggle={(e) => {
              e.stopPropagation();
              setEvidenceOpen(e.currentTarget.open);
            }}
          >
            <summary>Tier steps and profession evidence</summary>
            {evidenceOpen && <Evidence data={g} />}
          </details>
        </>
      )}
    </details>
  );
}
function RecipeRow({ recipe: r }: { recipe: Recipe }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <ItemLink id={r.output_item_id} name={r.name} />
      <p>
        <SkillBand text={r.skillup_band} /> · profit per craft{" "}
        <Money copper={r.profit_copper} />
      </p>
      <details
        onToggle={(e) => {
          e.stopPropagation();
          setOpen(e.currentTarget.open);
        }}
      >
        <summary>Cost and confidence evidence</summary>
        {open && <Evidence data={r} />}
      </details>
    </div>
  );
}
function TierRecipes({ recipes }: { recipes: Recipe[] }) {
  const priced = recipes.filter((r) => r.profit_copper !== null);
  const missing = recipes.filter((r) => r.profit_copper === null);
  return (
    <>
      {priced.slice(0, 3).map((r) => (
        <RecipeRow key={r.output_item_id} recipe={r} />
      ))}
      {priced.length > 3 && (
        <details>
          <summary>{priced.length - 3} more</summary>
          {priced.slice(3).map((r) => (
            <RecipeRow key={r.output_item_id} recipe={r} />
          ))}
        </details>
      )}
      {!!missing.length && (
        <details>
          <summary>{missing.length} with missing prices</summary>
          {missing.map((r) => (
            <div key={r.output_item_id}>
              <ItemLink id={r.output_item_id} name={r.name} />
              <p>
                <SkillBand text={r.skillup_band} /> · unknown · {r.board_reason}
              </p>
              <Evidence data={r} />
            </div>
          ))}
        </details>
      )}
    </>
  );
}
