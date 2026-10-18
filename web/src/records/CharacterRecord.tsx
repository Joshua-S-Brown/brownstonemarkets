import record from "./records.module.css";
import { Tile } from "../ui/Tile";
import { Panel } from "../ui/Panel";
import { SkillBar } from "../places/team/Roster";
import { utcLabel } from "../ui/UtcTime";
import { UtcTime } from "../ui/UtcTime";
import { Identity } from "../ui/Identity";
import { CharacterName } from "../ui/CharacterName";
import { lazy, Suspense, useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import * as Tabs from "@radix-ui/react-tabs";
import { get, post } from "../api/client";
import type { CharacterKey } from "../app/InspectorContext";
import { Evidence } from "../ui/Evidence";
import { Money } from "../places/team/Money";
import { ItemLink } from "../ui/ItemLink";
import { ErrorState, Pill, Tip } from "../ui/parts";
import { Link } from "react-router-dom";
import { PlanText } from "../places/today/PlanText";
import {
  type Plan,
  todayKey,
  readState,
  keepLocal,
  writeState,
} from "../places/today/state";
import type { components } from "../api/schema";
import { Path, Cost } from "../places/team/Path";
import { readWindow } from "../places/team/state";
import type { RecordData } from "../places/team/types";
const History = lazy(() =>
  import("./CharacterHistory").then((m) => ({ default: m.CharacterHistory })),
);
export function CharacterRecord({
  source,
  character,
}: {
  source: string;
  character: CharacterKey;
}) {
  const [tab, setTab] = useState("Next");
  const window = readWindow(source);
  const query = useQuery({
    queryKey: [source, "team-character", character, window],
    queryFn: ({ signal }) =>
      get<RecordData>(
        "team/character?" +
          new URLSearchParams({
            name: character[0],
            realm: character[1],
            faction: character[2],
            window: String(window),
          }),
        source,
        signal,
      ),
  });
  const plan = useQuery({
    queryKey: todayKey(source),
    queryFn: async ({ signal }) =>
      keepLocal(
        source,
        await post<Plan>(
          "today/plan",
          source,
          { state: { ...readState(source), window } },
          signal,
        ),
      ),
    staleTime: Infinity,
  });
  useEffect(() => {
    if (plan.data) writeState(source, plan.data.state);
  }, [source, plan.data]);
  const next = useQuery({
    queryKey: [
      source,
      "character-next",
      character,
      window,
      plan.data?.state.context,
      plan.data?.state.choices,
      plan.data?.state.queue_identity,
      plan.data?.state.refill,
    ],
    enabled: !!plan.data || !!plan.error,
    queryFn: ({ signal }) =>
      post<components["schemas"]["CharacterNext"]>(
        "team/character/next",
        source,
        {
          character,
          window,
          state: { ...(plan.data?.state ?? readState(source)), window },
        },
        signal,
      ),
  });
  if (query.error)
    return (
      <ErrorState
        source={source}
        error={query.error}
        retry={() => {
          void query.refetch();
        }}
      />
    );
  const data = query.data;
  if (!data) return <p role="status">Loading character…</p>;
  const c = data.card;
  const holdings = next.data?.holdings ?? data.holdings;
  return (
    <>
      <header className={record.header}>
        <h1>
          <CharacterName character={character} avatar />
        </h1>
        <p>
          Level {c.level ?? "unknown"} · last seen{" "}
          <UtcTime value={c.last_seen_utc} /> · {c.machine ?? "machine unknown"}
          {c.stale && (
            <>
              {" "}
              · <Pill tone="warn">stale</Pill>
            </>
          )}
        </p>
      </header>
      <div className={record.facts} aria-label="Character facts">
        <Tile label="Gold" value={<Money copper={c.gold_copper} />} />
        <Tile label="Professions" value={c.professions.length} />
        <Tile
          label="Known recipes"
          value={`${c.recipes_at_least ? "at least " : ""}${c.known_recipes}`}
        />
      </div>
      <Tabs.Root value={tab} onValueChange={setTab}>
        <Tabs.List aria-label="Character record">
          {["Next", "Professions", "Path", "Holdings", "History"].map((t) => (
            <Tabs.Trigger key={t} value={t}>
              {t}
            </Tabs.Trigger>
          ))}
        </Tabs.List>
        <Tabs.Content value="Next">
          <h2>Tonight’s Route</h2>
          {(plan.error || next.error) && (
            <p role="alert">{String(plan.error || next.error)}</p>
          )}
          {!plan.data && !plan.error && (
            <p role="status">Loading Today’s plan…</p>
          )}
          {next.data?.stops.map((stop, i) => (
            <section key={i}>
              <h3>
                <Dialog.Close asChild>
                  <Link
                    to={`/today?source=${encodeURIComponent(source)}&view=route`}
                  >
                    Route step {stop.number}
                  </Link>
                </Dialog.Close>{" "}
                · {stop.place}
              </h3>
              {stop.lines.map((line) => (
                <p key={line.index}>
                  <PlanText text={line.text} />
                </p>
              ))}
            </section>
          ))}
          {next.data && !next.data.stops.length && (
            <p>No steps for this character in tonight’s Route.</p>
          )}
          <h2>Next skill steps</h2>
          {data.progression.professions.map((g) => (
            <section key={g.profession}>
              <h3>{g.profession}</h3>
              {g.best ? (
                <>
                  <ItemLink id={g.best.output_item_id} name={g.best.name} />
                  <p>
                    needs skill {g.best.required_skill ?? "unknown"} ·{" "}
                    {g.best.learn_from}
                  </p>
                  <p>
                    Cost to reach: <Cost estimate={g.best.estimate} />
                  </p>
                  <p>
                    Earns <Money copper={g.best.profit_copper} /> per craft
                  </p>
                  <p>
                    {g.best.payback.status === "crafts"
                      ? `pays back training in ${g.best.payback.crafts} crafts`
                      : g.best.payback.status === "absent"
                        ? "Training cost unknown"
                        : `pays back training: ${g.best.payback.status}`}
                  </p>
                </>
              ) : (
                <p>
                  {g.note ||
                    (g.gathering
                      ? `${g.profession} levels by gathering, not crafting`
                      : "No valued recipe in reach")}
                </p>
              )}
            </section>
          ))}
          <h2>Last 7 UTC days</h2>
          <p>
            Came in:{" "}
            <Money
              copper={(next.data?.gold.in_copper as number | null) ?? null}
            />{" "}
            · Went out:{" "}
            <Money
              copper={(next.data?.gold.out_copper as number | null) ?? null}
            />{" "}
            · Net:{" "}
            <Money
              copper={(next.data?.gold.net_copper as number | null) ?? null}
            />
          </p>
          {(
            next.data?.gold.categories as
              | { category: string; in_copper: number; out_copper: number }[]
              | undefined
          )?.map((row) => (
            <p key={row.category}>
              {row.category} · in <Money copper={row.in_copper} /> · out{" "}
              <Money copper={row.out_copper} />
            </p>
          ))}
        </Tabs.Content>
        <Tabs.Content value="Professions">
          {!c.professions.length && <p>No profession reported yet.</p>}
          {c.professions.map((p) => (
            <section key={p.name} className={record.profession}>
              <SkillBar name={p.name} rank={p.rank} maximum={p.max_rank} />
              {p.at_cap && <Pill tone="warn">at cap: train the next tier</Pill>}
              <p>
                {p.rank != null && p.max_rank != null
                  ? p.max_rank - p.rank
                  : "unknown"}{" "}
                points before this tier caps
              </p>
              <Tip
                text={`Known recipes: ${p.known_count ?? "unknown"} · ${p.recipe_source} · Window list: ${Number.isFinite(Date.parse(p.recipes_at)) ? utcLabel(p.recipes_at) + " UTC" : "unknown"} · Seen crafted: ${p.seen_at && Number.isFinite(Date.parse(p.seen_at)) ? utcLabel(p.seen_at) + " UTC" : "unknown"}${p.possibly_incomplete ? " · possibly incomplete" : ""}`}
              >
                Recipe evidence
              </Tip>
            </section>
          ))}
        </Tabs.Content>
        <Tabs.Content value="Path">
          <Path groups={data.progression.professions} window={window} />
        </Tabs.Content>
        <Tabs.Content value="Holdings">
          <h2>Bags and bank</h2>
          <p>
            Total: {holdings.at_least || holdings.unpriced ? "at least " : ""}
            <Money copper={holdings.value_copper} /> · {holdings.unpriced}{" "}
            without a price
          </p>
          {!holdings.captures.length && <p>Bags and bank capture unknown.</p>}
          {["bags", "bank"].map((kind) => {
            const captures = holdings.captures.filter(
              (capture) => capture.kind === kind,
            );
            const atLeast =
              !captures.length ||
              captures.some((capture) => capture.unknown || capture.partial);
            return (
              <Panel
                key={kind}
                title={kind === "bags" ? "Bags" : "Bank"}
                subtitle={
                  atLeast
                    ? "at least · location unknown or partial"
                    : "Captured items"
                }
              >
                {holdings.items
                  .filter((item) => item.kind === kind)
                  .map((item, i) => (
                    <p key={i}>
                      <ItemLink
                        id={Number(item.item_id)}
                        name={String(item.name)}
                        variant={JSON.stringify([
                          item.variant_state,
                          item.variant_id,
                        ])}
                      />{" "}
                      · {atLeast ? "at least " : ""}
                      {String(item.units)} {item.units === 1 ? "unit" : "units"}{" "}
                      ·{" "}
                      {item.unit_copper == null ? (
                        "no price"
                      ) : (
                        <>
                          <Money copper={Number(item.unit_copper)} /> / unit ·{" "}
                          <Money copper={Number(item.value_copper)} /> total
                        </>
                      )}{" "}
                      · {String(item.action ?? "keep")}
                      {item.variant_state !== "base" && (
                        <>
                          ·{" "}
                          <Identity
                            state={
                              item.variant_state == null
                                ? null
                                : String(item.variant_state)
                            }
                          />
                        </>
                      )}
                    </p>
                  ))}
                {!holdings.items.some((item) => item.kind === kind) && (
                  <p>{atLeast ? "Contents unknown" : "No items captured"}</p>
                )}
              </Panel>
            );
          })}
        </Tabs.Content>
        <Tabs.Content value="History">
          <Suspense fallback={<p>Loading history…</p>}>
            <History rows={c.history} />
          </Suspense>
        </Tabs.Content>
      </Tabs.Root>
      <footer>
        <h2>Character evidence</h2>
        <details>
          <summary>Capture evidence</summary>
          <Evidence data={{ captures: holdings.captures }} />
        </details>
        <details>
          <summary>History evidence</summary>
          <Evidence data={{ history: c.history }} />
        </details>
        <Evidence
          data={{
            catalog_warnings: data.progression.catalog_warnings,
            unlisted: data.progression.unlisted,
          }}
        />
        <Evidence data={data.evidence} />
      </footer>
    </>
  );
}
