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
import { ErrorState, Pill } from "../ui/parts";
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
      <h1>
        <CharacterName character={character} />
      </h1>
      <p>
        Level {c.level ?? "unknown"} · Gold <Money copper={c.gold_copper} />
      </p>
      <p>
        <UtcTime value={c.last_seen_utc} /> · {c.machine ?? "machine unknown"}
        {c.stale && (
          <>
            {" "}
            · <Pill tone="warn">stale</Pill>
          </>
        )}
      </p>
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
            <section key={p.name}>
              <h2>
                {p.name} · {p.rank ?? "unknown"} / {p.max_rank ?? "unknown"}
              </h2>
              {p.at_cap && <Pill tone="warn">at cap: train the next tier</Pill>}
              <p>
                Known recipes: {p.known_count ?? "unknown"} · {p.recipe_source}{" "}
                · Window list: {p.recipes_at}
              </p>
              {p.possibly_incomplete && <p>possibly incomplete</p>}
              <p>Seen crafted: {p.seen_at ?? "unknown"}</p>
            </section>
          ))}
          <p>{c.skills_status}</p>
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
          {data.holdings.captures.map((capture, i) => (
            <section key={i}>
              <h3>
                {String(capture.kind)} ·{" "}
                {capture.unknown
                  ? "unknown"
                  : `${Number(capture.age_hours).toFixed(1)} hours old`}
                {Boolean(capture.partial) && " · partial"}
              </h3>
              <Evidence data={capture} />
            </section>
          ))}
          {data.holdings.items.map((item, i) => (
            <p key={i}>
              <ItemLink
                id={Number(item.item_id)}
                name={String(item.name)}
                variant={JSON.stringify([item.variant_state, item.variant_id])}
              />{" "}
              · {String(item.units)} · {String(item.kind)} ·{" "}
              <Identity
                state={
                  item.variant_state == null ? null : String(item.variant_state)
                }
              />
            </p>
          ))}
        </Tabs.Content>
        <Tabs.Content value="History">
          <Suspense fallback={<p>Loading history…</p>}>
            <History rows={c.history} />
          </Suspense>
        </Tabs.Content>
      </Tabs.Root>
      <footer>
        <h2>Character evidence</h2>
        <Evidence data={data.evidence} />
      </footer>
    </>
  );
}
