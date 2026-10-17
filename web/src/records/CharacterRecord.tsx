import record from "./records.module.css";
import { Tile } from "../ui/Tile";
import { Panel } from "../ui/Panel";
import { SkillBar } from "../places/team/Roster";
import { utcLabel } from "../ui/UtcTime";
import { UtcTime } from "../ui/UtcTime";
import { Identity } from "../ui/Identity";
import { CharacterName } from "../ui/CharacterName";
import { lazy, Suspense, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import * as Tabs from "@radix-ui/react-tabs";
import { get } from "../api/client";
import type { CharacterKey } from "../app/InspectorContext";
import { Evidence } from "../ui/Evidence";
import { Money } from "../places/team/Money";
import { ItemLink } from "../ui/ItemLink";
import { ErrorState, Pill, Tip } from "../ui/parts";
import { Path } from "../places/team/Path";
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
  const [tab, setTab] = useState("Professions");
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
          {["Professions", "Path", "Holdings", "History"].map((t) => (
            <Tabs.Trigger key={t} value={t}>
              {t}
            </Tabs.Trigger>
          ))}
        </Tabs.List>
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
          <Evidence
            data={{
              catalog_warnings: data.progression.catalog_warnings,
              unlisted: data.progression.unlisted,
            }}
          />
        </Tabs.Content>
        <Tabs.Content value="Holdings">
          <h2>Bags and bank</h2>
          {!data.holdings.captures.length && (
            <p>Bags and bank capture unknown.</p>
          )}
          {["bags", "bank"].map((kind) => {
            const captures = data.holdings.captures.filter(
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
                {data.holdings.items
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
                {!data.holdings.items.some((item) => item.kind === kind) && (
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
          <Evidence data={{ captures: data.holdings.captures }} />
        </details>
        <details>
          <summary>History evidence</summary>
          <Evidence data={{ history: c.history }} />
        </details>
        <Evidence data={data.evidence} />
      </footer>
    </>
  );
}
