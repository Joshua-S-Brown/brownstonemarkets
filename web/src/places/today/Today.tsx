import { useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { post } from "../../api/client";
import { Money } from "../../ui/Money";
import { Evidence } from "../../ui/Evidence";
import { ItemLink } from "../../ui/ItemLink";
import { Pill, Tip, ErrorState } from "../../ui/parts";
import { useInspector } from "../../app/InspectorContext";
import { type Plan, keepLocal, readState, writeState, todayKey } from "./state";
import { LevelUp } from "./LevelUp";
import { PlanText } from "./PlanText";
import { Settings } from "./Settings";
import { readWindow } from "../team/state";
import styles from "../../theme/app.module.css";
const views = ["route", "opportunities", "level-up"];
export function Today({
  source,
  waiting,
}: {
  source: string;
  waiting: number | null | undefined;
}) {
  const client = useQueryClient();
  const [params, setParams] = useSearchParams();
  const requested = params.get("view") || "route";
  const view = views.includes(requested) ? requested : "route";
  const inspect = useInspector();
  const query = useQuery({
    queryKey: todayKey(source),
    queryFn: async ({ signal }) =>
      keepLocal(
        source,
        await post<Plan>(
          "today/plan",
          source,
          { view, state: { ...readState(source), window: readWindow(source) } },
          signal,
        ),
      ),
    staleTime: Infinity,
  });
  const { refetch } = query;
  // The query already loads on mount; refetch only when the view changes (Level up loads lazily).
  const shownView = useRef(view);
  useEffect(() => {
    if (shownView.current === view) return;
    shownView.current = view;
    void refetch();
  }, [view, refetch]);
  const data = query.data;
  useEffect(() => {
    if (data) writeState(source, data.state);
  }, [data, source]);
  if (query.error)
    return (
      <ErrorState
        source={source}
        error={query.error}
        retry={() => {
          void refetch();
        }}
      />
    );
  if (!data) return <p role="status">Loading Today…</p>;
  const dataParams = new URLSearchParams(params);
  dataParams.set("source", source);
  dataParams.set("sheet", "data");
  const queue = data.plan.queue;
  const ticks = data.state.ticks || {};
  return (
    <>
      <div className={styles["section-heading"]}>
        <div>
          <p className={styles.eyebrow}>Tonight’s plan</p>
          <h1>Today</h1>
          <p>What should I do today to make gold?</p>
        </div>
        <Settings source={source} data={data} />
      </div>
      <div className={`${styles.tiles} ${styles["today-summary"]}`}>
        <div>
          Planned profit
          <strong>
            <Money copper={queue.expected_profit_copper} />
          </strong>
        </div>
        <div>
          Gold to spend
          <strong>
            <Money copper={queue.gold_needed_copper} /> /{" "}
            <Money copper={data.funds_copper} />
          </strong>
          <small>{data.funds_label}</small>
        </div>
        <div>
          Steps done
          <strong>
            {queue.lines.filter((_, i) => ticks[String(i)]).length} /{" "}
            {queue.lines.length}
          </strong>
        </div>
        <div>
          Data age
          <strong>
            {data.plan.freshness.upstream_known &&
            data.plan.freshness.age_hours !== null
              ? `${data.plan.freshness.age_hours.toFixed(1)} hours`
              : "Price age unknown"}
          </strong>
          <small>{waiting ?? "Unknown"} scans waiting</small>
        </div>
      </div>
      {data.plan.freshness.stale && (
        <p role="alert">
          Stale — inspect only. <a href={"?" + dataParams}>Open Data</a> to
          import a fresh scan.
        </p>
      )}
      {data.reset_note && <p role="status">{data.reset_note}</p>}
      <details>
        <summary>Funds and capture evidence</summary>
        {data.notes.map((n, i) => (
          <p key={i}>{n}</p>
        ))}
      </details>
      {data.plan.holdings_warning && <p>{data.plan.holdings_warning}</p>}
      {data.plan.dropped_choices.map((c, i) => (
        <p key={i}>
          {(data.state.rows || []).find(
            (r) => r.catalog_id === c.catalog_id && r.recipe_id === c.recipe_id,
          )?.output_name || `Recipe ${c.recipe_id}`}
          : {c.reason}
        </p>
      ))}
      <div role="tablist" aria-label="Today views">
        {views.map((v) => (
          <button
            key={v}
            role="tab"
            aria-selected={view === v}
            onClick={() => {
              const next = new URLSearchParams(params);
              next.set("view", v);
              setParams(next);
            }}
          >
            {v === "level-up"
              ? "Level up"
              : v === "route"
                ? "Route"
                : "Opportunities"}
          </button>
        ))}
      </div>
      {view === "route" && (
        <>
          <p>{queue.mail_note}</p>
          {data.stops.length === 0 && (
            <p>
              No funded crafts. Open settings or inspect the plan evidence
              below.
            </p>
          )}
          <ol className={styles["route-list"]}>
            {data.stops.map((stop, i) => (
              <li key={i} className={styles["route-stop"]}>
                <h2>
                  {i + 1}.{" "}
                  {(stop.characters || []).length
                    ? stop.characters.map((c) => (
                        <button
                          key={c.join("|")}
                          onClick={() => inspect({ character: c })}
                        >
                          {c.join(" · ")}
                        </button>
                      ))
                    : stop.character}
                  · {stop.place}
                </h2>
                {stop.lines.map((line) => (
                  <div key={line.index}>
                    <label className={styles["route-line"]}>
                      <input
                        type="checkbox"
                        checked={!!ticks[String(line.index)]}
                        onChange={(e) => {
                          const state = {
                            ...data.state,
                            ticks: {
                              ...ticks,
                              [String(line.index)]: e.target.checked,
                            },
                          };
                          writeState(source, state);
                          client.setQueryData(todayKey(source), {
                            ...data,
                            state,
                          });
                        }}
                      />
                      <span>
                        <PlanText text={line.text} />
                      </span>
                    </label>
                    {line.warnings && <p>{line.warnings}</p>}
                    <details>
                      <summary>Line evidence</summary>
                      <Evidence data={line.evidence} />
                    </details>
                  </div>
                ))}
              </li>
            ))}
          </ol>
          <button
            onClick={() => {
              void navigator.clipboard.writeText(data.copy_text);
            }}
          >
            Copy as text
          </button>
          <details>
            <summary>Queue text and totals</summary>
            <pre className={styles["queue-text"]}>{data.copy_text}</pre>
          </details>
        </>
      )}
      {view === "opportunities" && (
        <>
          <label>
            <input
              type="checkbox"
              checked={!!data.state.hide_low}
              onChange={(e) => {
                const state = { ...data.state, hide_low: e.target.checked };
                writeState(source, state);
                client.setQueryData(todayKey(source), { ...data, state });
              }}
            />
            Hide Low confidence
          </label>
          <p>
            {data.state.hide_low
              ? data.plan.craft.filter((r) => r.confidence === "Low").length
              : 0}{" "}
            Low confidence crafts hidden; the complete Route is retained.
          </p>
          <p>
            Open an item’s Our move panel to adjust its batch, choice, or
            refill.
          </p>
          {data.plan.craft
            .filter((row) => !data.state.hide_low || row.confidence !== "Low")
            .map((row) => (
              <section
                key={row.catalog_id + row.recipe_id}
                className={styles["route-stop"]}
              >
                <h2>
                  <ItemLink id={row.output_item_id} name={row.output_name} />
                </h2>
                <p>
                  <Money copper={row.headline_per_craft_copper} /> per craft
                  {row.profit_basis} · {row.batch_size} crafts ·{" "}
                  {row.made_by || "Maker unknown"}
                </p>
                {row.warnings_text && <p>{row.warnings_text}</p>}
                <Tip text={row.confidence_reasons.join("; ")}>
                  <Pill>{row.confidence} confidence</Pill>
                </Tip>
              </section>
            ))}
          {(data.state.rows || [])
            .filter(
              (r) =>
                !data.plan.craft.some(
                  (c) =>
                    c.catalog_id === r.catalog_id &&
                    c.recipe_id === r.recipe_id,
                ),
            )
            .map((row) => (
              <p key={row.catalog_id + row.recipe_id}>
                <ItemLink id={row.output_item_id} name={row.output_name} /> ·
                not in tonight’s plan; open it to include it again.
              </p>
            ))}
        </>
      )}
      {view === "level-up" &&
        (query.isFetching || !data.session ? (
          <p role="status">Loading Level up…</p>
        ) : (
          <LevelUp session={data.session} />
        ))}
      <details>
        <summary>How this plan was made</summary>
        <Evidence data={{ ...data.evidence, plan: data.plan }} />
      </details>
    </>
  );
}
