import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { get } from "../../api/client";
import { useInspector } from "../../app/InspectorContext";
import { Money } from "./Money";
import { Evidence } from "../../ui/Evidence";
import { ErrorState, Pill, Tip } from "../../ui/parts";
import { readWindow, writeWindow } from "./state";
import { NextStep } from "./Path";
import { Hire, title } from "./Hiring";
import type { TeamData } from "./types";
import styles from "../../theme/app.module.css";
export function Team({ source }: { source: string }) {
  const [window, setWindow] = useState(() => readWindow(source));
  const [draft, setDraft] = useState(window);
  const inspect = useInspector();
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
      <p className={styles["eyebrow"]}>Our team</p>
      <h1>Team</h1>
      <p>Who makes what, and where are the gaps?</p>
      <label>
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
      <p>Updates when you let go.</p>
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
          <div className={styles["summary-strip"]}>
            <Pill>{data.roster.length} characters</Pill>
            <Pill>
              Last seen {data.roster[0]?.card.last_seen_relative ?? "unknown"} ·{" "}
              {data.roster[0]?.card.machine ?? "machine unknown"}
            </Pill>
            <Tip text={data.evidence.finished_at ?? "Scan capture unknown"}>
              <Pill>
                {!data.evidence.freshness
                  ? "No scan"
                  : !data.evidence.freshness.upstream_known
                    ? "Price age unknown"
                    : data.evidence.freshness.stale
                      ? "Stale scan"
                      : "Fresh scan"}
              </Pill>
            </Tip>
          </div>
          {data.notes.map((n, i) => (
            <p key={i} role="status">
              {n}
            </p>
          ))}
          {!data.roster.length && (
            <p>No characters imported for this source. Use Data → Import.</p>
          )}
          <div className={styles["team-roster"]}>
            {data.roster.map(({ character, card, progression }) => (
              <article
                className={styles["team-card"]}
                onClick={(e) => {
                  if (!(e.target as HTMLElement).closest("button,a"))
                    inspect({ character });
                }}
                key={character.join("|")}
              >
                <button
                  className={styles["team-name"]}
                  onClick={() => inspect({ character })}
                >
                  {card.name} · {card.realm}
                </button>
                <Tip
                  text={`${card.last_seen_utc} · ${card.machine ?? "machine unknown"}`}
                >
                  <span>{card.last_seen_relative}</span>
                </Tip>
                <p>
                  Level {card.level ?? "unknown"} · Gold{" "}
                  <Money copper={card.gold_copper} />
                  {card.stale && (
                    <>
                      {" "}
                      · <Pill tone="warn">stale</Pill>
                    </>
                  )}
                </p>
                {card.professions.map((p) => (
                  <p key={p.name}>
                    {p.name} · {p.rank ?? "unknown"} / {p.max_rank ?? "unknown"}
                    {p.at_cap && (
                      <>
                        {" "}
                        · <Pill tone="warn">at cap: train the next tier</Pill>
                      </>
                    )}
                  </p>
                ))}
                {!card.professions.length && (
                  <p>
                    No profession reported yet. Next: learn a profession to see
                    what’s in reach.
                  </p>
                )}
                {progression.professions.map((g) => (
                  <NextStep key={g.profession} group={g} />
                ))}
                {!progression.professions.length &&
                  !!card.professions.length && (
                    <p>Next step · current scan unavailable</p>
                  )}
              </article>
            ))}
          </div>
          <h2>Profession coverage</h2>
          {data.hires.map((r) => (
            <p key={r.profession}>
              {title(r.profession)} ·{" "}
              {r.holders.length
                ? r.holders
                    .map(
                      (h) =>
                        `${h.character.join(" · ")} ${h.rank ?? "unknown"} / ${h.max_rank ?? "unknown"}`,
                    )
                    .join("; ")
                : "not covered"}
            </p>
          ))}
          {data.no_catalog.map((n) => (
            <p key={n}>
              {title(n)} · no catalog: gathering income and supply are not
              modelled
            </p>
          ))}
          <h2>Add a character?</h2>
          <p>{data.hiring_labels}</p>
          {data.all_incomplete && (
            <p>
              Cost to 300 is incomplete for every profession; open one to see
              why
            </p>
          )}
          {data.hires.map((row) => (
            <Hire
              key={row.profession}
              row={row}
              source={source}
              showCost={!data.all_incomplete}
            />
          ))}
          <h2>Instead of a new hire</h2>
          <p>
            Two primary professions: Classic Era limit, unconfirmed on Forever.
            Comparison only; no recommendation to drop a profession. Secondary
            skills use no slot. Best reachable profit within {window} points
            (CRAFT-11).
          </p>
          {!data.comparisons.length && (
            <p>No character has two evidenced primary professions.</p>
          )}
          {data.comparisons.map((c) => (
            <section key={c.character.join("|")}>
              <button onClick={() => inspect({ character: c.character })}>
                {c.character.join(" · ")}
              </button>
              {c.professions.map((p) => (
                <p key={p.profession}>
                  {title(p.profession)} ·{" "}
                  <Money copper={p.best?.profit_copper ?? null} /> per craft
                </p>
              ))}
            </section>
          ))}
          <details>
            <summary>How these estimates work</summary>
            <p>{data.labels}</p>
            <Evidence data={data.evidence} />
          </details>
        </>
      )}
    </>
  );
}
