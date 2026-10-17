import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { post } from "../../api/client";
import { PageHead } from "../../ui/PageHead";
import { Panel } from "../../ui/Panel";
import { Tile } from "../../ui/Tile";
import { Money } from "../../ui/Money";
import { Evidence } from "../../ui/Evidence";
import { ErrorState } from "../../ui/parts";
import { type Plan, keepLocal, readState, writeState, todayKey } from "./state";
import { LevelUp } from "./LevelUp";
import { Route } from "./Route";
import { Opportunities } from "./Opportunities";
import { Settings } from "./Settings";
import { readWindow } from "../team/state";
import styles from "../../ui/components.module.css";
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
  const [dismissed, dismiss] = useState("");
  const opportunities = useRef<HTMLDivElement>(null);
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
  const ready = !!query.data;
  useEffect(() => {
    if (view === "opportunities" && ready)
      opportunities.current?.scrollIntoView?.({ block: "start" });
  }, [view, ready]);
  const { refetch } = query;
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
  // This request starts only after the Route has committed. Its errors/loading never replace the Route.
  const level = useQuery({
    queryKey: [
      source,
      "today-lever",
      data?.state.context,
      data?.state.choices,
      data?.state.queue_identity,
      data?.state.refill,
      readWindow(source),
    ],
    enabled: !!data,
    queryFn: ({ signal }) =>
      post<Plan>(
        "today/plan",
        source,
        {
          view: "level-up",
          state: { ...readState(source), window: readWindow(source) },
        },
        signal,
      ),
    staleTime: Infinity,
  });
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
  const resetKey = `${source}:${data.state.context}:${data.reset_note}`;
  const queue = data.plan.queue;
  const ticks = data.state.ticks || {};
  const done = queue.lines.filter((_, i) => ticks[String(i)]).length;
  const update = (state: Plan["state"]) => {
    writeState(source, state);
    client.setQueryData(todayKey(source), { ...data, state });
  };
  const setView = (v: string) => {
    const next = new URLSearchParams(params);
    next.set("view", v);
    setParams(next);
  };
  return (
    <>
      <PageHead
        eyebrow="Tonight’s plan"
        title="Today"
        subtitle="What should I do today to make gold?"
        action={<Settings source={source} data={data} />}
      />
      <div className={styles.kpis}>
        <Tile
          label="Gold to spend"
          value={
            <>
              <Money copper={queue.gold_needed_copper} />{" "}
              <small>
                of <Money copper={data.funds_copper} />
              </small>
            </>
          }
          caption={data.funds_label.split(";")[0]}
          progress={
            data.funds_copper > 0
              ? queue.gold_needed_copper / data.funds_copper
              : null
          }
        />
        <Tile
          label="Progress"
          value={`${done} of ${queue.lines.length} steps`}
          caption="Follow the Route below"
          progress={queue.lines.length ? done / queue.lines.length : null}
        />
        <Tile
          label="Data age"
          value={
            data.plan.freshness.upstream_known &&
            data.plan.freshness.age_hours !== null
              ? `${data.plan.freshness.age_hours.toFixed(1)} hours`
              : "Price age unknown"
          }
          caption={
            waiting == null
              ? "Waiting scans not checked"
              : `${waiting} ${waiting === 1 ? "scan" : "scans"} waiting`
          }
        />
        <Tile
          label="Planned profit"
          value={<Money copper={queue.expected_profit_copper} />}
          caption="At planned undercut · listings, not sales"
        />
      </div>
      {data.plan.freshness.stale && (
        <p role="alert">
          Stale — inspect only. <a href={"?" + dataParams}>Open Data</a> to
          import a fresh scan.
        </p>
      )}
      {data.reset_note && resetKey !== dismissed && (
        <div role="status">
          {data.reset_note}
          <button onClick={() => dismiss(resetKey)}>
            Dismiss reset notice
          </button>
        </div>
      )}
      {data.plan.dropped_choices.map((c, i) => (
        <p key={i}>
          {data.state.rows?.find(
            (r) => r.catalog_id === c.catalog_id && r.recipe_id === c.recipe_id,
          )?.output_name || "Requested recipe"}
          : {c.reason}
        </p>
      ))}
      <div role="tablist" aria-label="Today views" className={styles.tabs}>
        {views.map((v) => (
          <button
            key={v}
            role="tab"
            data-view={v}
            aria-selected={view === v}
            onClick={() => setView(v)}
          >
            {v === "level-up"
              ? "Level up"
              : v === "route"
                ? "Route"
                : "Opportunities"}
          </button>
        ))}
      </div>
      {view !== "level-up" && (
        <div className={styles["today-grid"]}>
          <Panel
            title="Route"
            subtitle={`${queue.lines.length} steps`}
            action={
              <button
                className={styles.primary}
                onClick={() => {
                  void navigator.clipboard.writeText(data.copy_text);
                }}
              >
                Copy as text
              </button>
            }
          >
            <Route
              data={data}
              tick={(index, checked) =>
                update({
                  ...data.state,
                  ticks: { ...ticks, [String(index)]: checked },
                })
              }
            />
          </Panel>
          <div ref={opportunities}>
            <Panel title="Opportunities" subtitle="Tonight and what comes next">
              <Opportunities
                data={data}
                source={source}
                session={data.session || level.data?.session}
                openLevel={() => setView("level-up")}
                hideLow={(hide_low) => update({ ...data.state, hide_low })}
              />
            </Panel>
          </div>
        </div>
      )}
      {view === "level-up" &&
        (data.session || level.data?.session ? (
          <LevelUp session={(data.session || level.data?.session)!} />
        ) : (
          <p role="status">Loading Level up…</p>
        ))}
      <details>
        <summary>How this plan was made</summary>
        <Evidence
          data={{
            ...data.evidence,
            funds_label: data.funds_label,
            notes: data.notes,
            plan: data.plan,
          }}
        />
      </details>
    </>
  );
}
