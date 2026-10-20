import { PageHead } from "../../ui/PageHead";
import { Panel } from "../../ui/Panel";
import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { get } from "../../api/client";
import { Evidence } from "../../ui/Evidence";
import { ErrorState, Tip } from "../../ui/parts";
import { readWindow, writeWindow } from "./state";
import { Money } from "./Money";
import { title } from "./Hiring";
import { MemberCard } from "./Roster";
import { Coverage } from "./Coverage";
import { TeamEarnings } from "./Earnings";
import { HiringTables } from "./HiringTables";
import type { TeamData } from "./types";
import styles from "./team.module.css";
export function Team({ source }: { source: string }) {
  const [window, setWindow] = useState(() => readWindow(source));
  const [draft, setDraft] = useState(window);
  const query = useQuery({
    queryKey: [source, "team", window],
    placeholderData: keepPreviousData,
    queryFn: ({ signal }) =>
      get<TeamData>("team?window=" + window, source, signal),
  });
  function commit() {
    writeWindow(source, draft);
    setWindow(draft);
  }
  const data = query.data;
  return (
    <>
      <PageHead
        eyebrow={`${data?.roster.length ?? "Our"} characters · captured from the addon`}
        title="Team"
        subtitle="Who makes what, and where are the gaps?"
      />
      {query.error && (
        <ErrorState
          source={source}
          error={query.error}
          retry={() => {
            void query.refetch();
          }}
        />
      )}
      {!data && !query.error && <p role="status">Loading Team…</p>}
      {data && (
        <>
          {data.notes.map((n, i) => (
            <p key={i} role="status">
              {n}
            </p>
          ))}
          <div className={styles.panels}>
            <Panel title="Capital">
              <p>
                Gold: <Money copper={data.capital.gold_copper} /> · Holdings:{" "}
                <Money copper={data.capital.holdings_copper} /> · Total:{" "}
                {data.capital.at_least && "at least "}
                <Money copper={data.capital.total_copper} />
              </p>
              {data.capital.missing_gold > 0 && (
                <p>
                  {data.capital.missing_gold} characters without captured gold
                </p>
              )}
              {data.capital.unpriced > 0 && (
                <p>{data.capital.unpriced} stacks without a price</p>
              )}
              {data.capital.holdings_incomplete && (
                <p>Holdings captures are unknown or partial.</p>
              )}
              <p>Mailboxes: not captured</p>
              <details>
                <summary>Capital by character · Auctions not valued</summary>
                {data.capital.characters.map((c) => (
                  <p key={c.character.join("|")}>
                    {c.character[0]} · Gold: <Money copper={c.gold_copper} /> ·
                    Holdings: <Money copper={c.holdings_copper} /> · Total:{" "}
                    {c.at_least && "at least "}
                    <Money copper={c.total_copper} /> · Auctions:{" "}
                    {c.auctions ?? "unknown"} · not valued
                  </p>
                ))}
              </details>
            </Panel>
            <Panel
              title="Roster"
              action={
                <label className={styles.window}>
                  Look ahead · {draft} points
                  <input
                    aria-label="Points within reach"
                    type="range"
                    min="5"
                    max="100"
                    step="1"
                    value={draft}
                    onChange={(e) => setDraft(Number(e.target.value))}
                    onPointerUp={commit}
                    onKeyUp={commit}
                    onBlur={commit}
                  />
                </label>
              }
            >
              {!data.roster.length && !data.planned.length && (
                <p>
                  No characters imported for this source. Use Data → Import.
                </p>
              )}
              <div className={styles.roster}>
                {data.roster.map((m) => (
                  <MemberCard key={m.character.join("|")} member={m} />
                ))}
                {data.planned.map((m, i) => (
                  <article className={styles.card} key={i}>
                    <header>
                      <div>
                        <strong>{m.name ?? "Unnamed character"}</strong>
                        <div className={styles.meta}>
                          Planned, not created · {m.faction}
                        </div>
                      </div>
                    </header>
                    <p>{m.role}</p>
                    {m.professions.map((p) => (
                      <section key={p.profession}>
                        <h3>{title(p.profession)}</h3>
                        {p.tiers.map((t) => (
                          <p key={t.cap}>
                            Cost to {t.cap}:{" "}
                            <Money copper={t.estimate.cost_copper ?? null} />
                            {!t.estimate.complete && (
                              <>
                                {" "}
                                <Tip text={t.estimate.reasons.join("; ")}>
                                  Incomplete estimate
                                </Tip>
                              </>
                            )}{" "}
                            · best profit per craft:{" "}
                            <Money copper={t.best?.profit_copper ?? null} />
                          </p>
                        ))}
                      </section>
                    ))}
                  </article>
                ))}
              </div>
            </Panel>
            {data.earnings && <TeamEarnings data={data.earnings} />}
            <Coverage data={data} />
            <HiringTables data={data} source={source} window={window} />
          </div>
          <details>
            <summary>How these estimates work</summary>
            <p>{data.labels}</p>
            <p>{data.hiring_labels}</p>
            <p>
              Two primary professions: Classic Era limit, unconfirmed on
              Forever. Comparison only; no recommendation to drop a profession.
              Secondary skills use no slot.
            </p>
            {data.all_incomplete && (
              <p>
                Cost to 300 is incomplete for every profession; open one to see
                why
              </p>
            )}
            <Evidence data={data.evidence} />
          </details>
        </>
      )}
    </>
  );
}
