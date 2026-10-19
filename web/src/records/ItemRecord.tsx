import { RemovalSpeed } from "../ui/RemovalSpeed";
import record from "./records.module.css";
import { Tile } from "../ui/Tile";
import { Panel } from "../ui/Panel";
import { SignalPill, isSignal } from "../ui/SignalPill";
import { Identity } from "../ui/Identity";
import { UtcTime } from "../ui/UtcTime";
import styles from "../theme/app.module.css";
import { lazy, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import * as Tabs from "@radix-ui/react-tabs";
import type { Activity } from "../api/market";
import { get, type Item } from "../api/client";
import { Money } from "../ui/Money";
import { ItemLink } from "../ui/ItemLink";
import { ErrorState, Pill } from "../ui/parts";
import { OurMove } from "../places/today/OurMove";
import { Evidence } from "../ui/Evidence";
import {
  ItemChain,
  ItemActivity,
  ItemGathering,
  actionWords,
} from "./ItemDetails";
// Recharts loads with the record, keeping it out of the shell's first bundle.
const ItemCharts = lazy(() =>
  import("./ItemCharts").then((m) => ({ default: m.ItemCharts })),
);
const loadingCharts = <p role="status">Loading charts…</p>;
export function ItemRecord({
  id,
  source,
  variant,
}: {
  id: number;
  source: string;
  variant?: string;
}) {
  const query = useQuery({
    queryKey: [source, "item", id, variant],
    queryFn: ({ signal }) =>
      get<Item>(
        `items/${id}${variant ? "?variant=" + encodeURIComponent(variant) : ""}`,
        source,
        signal,
      ),
    enabled: !!source,
  });
  const activity = useQuery({
    queryKey: [source, "activity", id],
    queryFn: ({ signal }) =>
      get<Activity>(`items/${id}/activity`, source, signal),
    enabled: !!source,
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
  if (!query.data) return <p role="status">Loading saved item…</p>;
  const item = query.data;
  return (
    <>
      <header className={record.header}>
        <h1>
          <ItemLink id={id} name={item.name} quality={item.quality} badge />
        </h1>
        <p>
          {item.role ?? "Outside compatible catalogs"} · {item.item_id}
          {variant && (
            <>
              {" "}
              · <Identity state={JSON.parse(variant)[0]} several />
            </>
          )}
        </p>
        <div>
          {item.crowding && isSignal(item.crowding) && (
            <SignalPill label={item.crowding} />
          )}{" "}
          {item.overshoot && isSignal(item.overshoot) && (
            <SignalPill label={item.overshoot} />
          )}
        </div>
      </header>
      <div className={record.facts} aria-label="Item facts">
        <Tile label="Lowest" value={<Money copper={item.price_copper} />} />
        <Tile label="Typical" value={<Money copper={item.typical_copper} />} />
        <Tile
          label="Listings · units"
          value={`${item.listings?.toLocaleString() ?? "unknown"} · ${item.units?.toLocaleString() ?? "unknown"}`}
        />
      </div>
      <Tabs.Root defaultValue="overview">
        <Tabs.List aria-label="Item tabs">
          <Tabs.Trigger value="overview">Overview</Tabs.Trigger>
          <Tabs.Trigger value="history">Price history</Tabs.Trigger>
          <Tabs.Trigger value="listings">Listings</Tabs.Trigger>
          <Tabs.Trigger value="chain">Made from and used in</Tabs.Trigger>
          <Tabs.Trigger value="activity">Our activity</Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="overview">
          <Suspense fallback={loadingCharts}>
            <ItemCharts
              source={source}
              id={id}
              overview
              typical={item.typical_copper}
            />
          </Suspense>
          <dl className={record.kv}>
            <dt>Where to get it</dt>
            <dd>
              {item.vendor_buy.length ? "Vendor · " : ""}
              {[
                ...new Set(
                  activity.data?.farming.flatMap((c) =>
                    c.farming.rows.map((r) => r.zone || "unknown zone"),
                  ) ?? [],
                ),
              ].join(" · ") || "not gathered yet"}{" "}
              · <a href="#item-gathering">Gathering evidence below</a>
            </dd>
            <dt>Vendor buy</dt>
            <dd>
              {item.vendor_buy.length
                ? item.vendor_buy.map((v, i) => (
                    <span key={i}>
                      {i ? " / " : ""}
                      <Money copper={v} />
                    </span>
                  ))
                : "unknown"}
            </dd>
            <dt>Vendor sell</dt>
            <dd>
              <Money copper={item.vendor_sell} />
            </dd>
            <dt>24h post deposit, one</dt>
            <dd>
              <Money copper={item.deposit_copper ?? null} /> · refunded on sale,
              lost if it expires
            </dd>
            <dt>Team holdings</dt>
            <dd>
              {item.at_least ? "at least " : ""}
              {item.held ?? "unknown"} units
              {item.held !== null &&
                !!activity.data?.holdings.length &&
                ` · ${activity.data.holdings
                  .map(
                    (h) =>
                      `${h.character}${h.kind === "bags" ? "" : ` ${h.kind}`} ${h.units}`,
                  )
                  .join(", ")}`}
            </dd>
          </dl>
          <Panel title="Removal rate">
            <RemovalSpeed speed={item.speed} />
          </Panel>
          <Panel title="Best use">
            {(["used_in", "made_from"] as const).map((key) => (
              <section key={key}>
                <h3>{key === "used_in" ? "Used in" : "Made from"}</h3>
                {item[key].item_id ? (
                  <>
                    <ItemLink id={item[key].item_id!} name={item[key].name!} />
                    <p>
                      Profit per craft:{" "}
                      <Money copper={item[key].profit_copper ?? null} />
                    </p>
                  </>
                ) : (
                  <p>No profitable use known</p>
                )}
                <details>
                  <summary>Route evidence</summary>
                  <Evidence
                    data={{
                      reason: actionWords(item[key].reason),
                    }}
                  />
                </details>
              </section>
            ))}
          </Panel>
          {(!variant || ["base", null].includes(JSON.parse(variant)[0])) && (
            <OurMove source={source} id={id} />
          )}
          <div id="item-gathering">
            <Panel title="Farming spots">
              <ItemGathering source={source} id={id} />
            </Panel>
          </div>
        </Tabs.Content>
        <Tabs.Content value="history">
          <Suspense fallback={loadingCharts}>
            <ItemCharts source={source} id={id} />
          </Suspense>
        </Tabs.Content>
        <Tabs.Content value="listings">
          <Suspense fallback={loadingCharts}>
            <ItemCharts source={source} id={id} listings />
          </Suspense>
        </Tabs.Content>
        <Tabs.Content value="chain">
          <p>
            Catalog routes describe the base item. Variant quotes never enter
            these calculations.
          </p>
          <ItemChain source={source} id={id} />
        </Tabs.Content>
        <Tabs.Content value="activity">
          <p>Base-item holdings and own journal outcomes.</p>
          <ItemActivity source={source} id={id} />
        </Tabs.Content>
      </Tabs.Root>
      <footer className={styles["evidence"]}>
        <Pill
          tone={
            item.evidence.freshness?.stale
              ? "warn"
              : item.evidence.freshness?.upstream_known
                ? "good"
                : "neutral"
          }
        >
          {!item.evidence.freshness
            ? "No scan"
            : !item.evidence.freshness.upstream_known
              ? "Price age unknown"
              : item.evidence.freshness.stale
                ? "Stale"
                : "Fresh"}
        </Pill>
        <p>
          Scan {item.evidence.scan_id ?? "unavailable"}
          <br />
          Finished <UtcTime value={item.evidence.finished_at} />
        </p>
        {item.evidence.freshness && (
          <p>
            {item.evidence.freshness.upstream_known
              ? `${Number(item.evidence.freshness.age_hours).toFixed(1)} hours since scan`
              : "Price age unknown · collection time only"}
          </p>
        )}
        <details>
          <summary>Identity and evidence</summary>
          <Evidence data={item.details} />
        </details>
        <p>
          {source}
          <br />
          {item.evidence.market_id}
        </p>
      </footer>
    </>
  );
}
