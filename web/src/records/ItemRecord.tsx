import styles from "../theme/app.module.css";
import { lazy, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import * as Tabs from "@radix-ui/react-tabs";
import { get, type Item } from "../api/client";
import { Money } from "../ui/Money";
import { ItemLink } from "../ui/ItemLink";
import { ErrorState, Pill } from "../ui/parts";
import { Evidence } from "../ui/Evidence";
import { ItemChain, ItemActivity, ItemGathering } from "./ItemDetails";
// Recharts loads only when a chart tab opens, keeping it out of the shell's first bundle.
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
  const counts = [
    ["Units listed", item.units],
    ["Listings", item.listings],
    ["Held by the team", item.held],
  ] as const;
  return (
    <>
      <p className={styles["eyebrow"]}>Item record · {item.item_id}</p>
      <h1>
        <ItemLink id={id} name={item.name} quality={item.quality} />
      </h1>
      <p className={styles["muted"]}>
        Quality {item.quality ?? "unknown"} ·{" "}
        {variant ? JSON.parse(variant).join(" · ") : "base-item Overview"}
      </p>
      <Tabs.Root defaultValue="overview">
        <Tabs.List aria-label="Item tabs">
          <Tabs.Trigger value="overview">Overview</Tabs.Trigger>
          <Tabs.Trigger value="history">Price history</Tabs.Trigger>
          <Tabs.Trigger value="listings">Listings</Tabs.Trigger>
          <Tabs.Trigger value="chain">Made from and used in</Tabs.Trigger>
          <Tabs.Trigger value="activity">Our activity</Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="overview">
          <div className={styles["tiles"]}>
            <div>
              Price now / unit
              <strong>
                <Money copper={item.price_copper} />
              </strong>
            </div>
            <div>
              Typical / unit
              <strong>
                <Money copper={item.typical_copper} />
              </strong>
            </div>
            {counts.map(([label, value]) => (
              <div key={label}>
                {label}
                <strong>
                  {label === "Held by the team" && item.at_least
                    ? "at least "
                    : ""}
                  {value ?? "unknown"}
                </strong>
              </div>
            ))}
            <div>
              Vendor buy / unit
              <strong>
                {item.vendor_buy.length
                  ? item.vendor_buy.map((v, i) => (
                      <span key={i}>
                        {i ? " / " : ""}
                        <Money copper={v} />
                      </span>
                    ))
                  : "unknown"}
              </strong>
            </div>
            <div>
              Vendor sell / unit
              <strong>
                <Money copper={item.vendor_sell} />
              </strong>
            </div>
          </div>
          {item.crowding && <Pill>{item.crowding}</Pill>}{" "}
          {item.overshoot && <Pill>{item.overshoot}</Pill>}
          <h2>Best use in our catalogs</h2>
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
              <p className={styles["muted"]}>{item[key].reason}</p>
            </section>
          ))}
          <ItemGathering source={source} id={id} />
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
          Finished {item.evidence.finished_at ?? "unknown"}
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
