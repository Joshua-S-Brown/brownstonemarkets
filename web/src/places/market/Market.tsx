import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import type { ColumnDef, SortingState } from "@tanstack/react-table";
import type { components } from "../../api/schema";
import { get } from "../../api/client";
import type { Market as MarketData, Row, Signal } from "../../api/market";
import { PageHead } from "../../ui/PageHead";
import { Panel } from "../../ui/Panel";
import { SignalPill, isSignal } from "../../ui/SignalPill";
import { Identity } from "../../ui/Identity";
import { Money } from "../../ui/Money";
import { ItemLink } from "../../ui/ItemLink";
import { BetaQuote } from "../../ui/BetaQuote";
import { UtcTime, utcLabel } from "../../ui/UtcTime";
import { Tip, Sparkline, ErrorState } from "../../ui/parts";
import { DataGrid } from "../../ui/DataGrid";
import { Evidence } from "../../ui/Evidence";
import { readWindow } from "../team/state";
import styles from "./market.module.css";
export function signalEvidence(s: Signal) {
  return `${s.listings} listings · ${s.units} units · largest stack ${s.largest_stack_units}/${s.units} · lowest buyout changes ${s.churn.changed}/${s.churn.pairs} comparable gaps${s.churn.pairs ? "" : " (churn unknown)"} · ${s.overshoot.days} days, ${s.overshoot.scans} scans · ${s.overshoot.label}`;
}
export function identityVariant(row: {
  variant_state: string | null;
  variant_id: string | null;
}) {
  return JSON.stringify([row.variant_state, row.variant_id]);
}
function Percent({ value }: { value: number | null }) {
  return (
    <span
      className={styles.percent}
      data-direction={
        value == null || value === 0 ? "unknown" : value < 0 ? "cheap" : "high"
      }
    >
      {value == null
        ? "unknown"
        : `${value > 0 ? "+" : ""}${value.toFixed(1)}%`}
    </span>
  );
}
function Trend({ values, name }: { values: (number | null)[]; name: string }) {
  return values.filter((v) => v !== null).length >= 2 ? (
    <Sparkline values={values} label={`${name} stored lowest buyout`} />
  ) : (
    <span className={styles.muted} title="Two priced stored points needed">
      —
    </span>
  );
}
const columns: ColumnDef<Row>[] = [
  {
    accessorKey: "name",
    header: "Item",
    cell: ({ row: { original: r } }) => (
      <>
        <ItemLink
          id={r.item_id}
          name={r.name}
          quality={r.quality}
          badge
          variant={identityVariant(r)}
        />
        <small>
          {r.item_id} <Identity state={r.variant_state} />
        </small>
      </>
    ),
  },
  ...(["price_copper", "typical_copper"] as const).map((key, i) => ({
    id: key,
    accessorFn: (r: Row) => r[key] ?? undefined,
    header: ["Lowest", "Typical"][i],
    sortUndefined: "last" as const,
    cell: ({ row: { original: r } }: { row: { original: Row } }) => (
      <Money copper={r[key]} />
    ),
  })),
  {
    id: "gap_percent",
    header: "vs typical",
    accessorFn: (r) => r.gap_percent ?? undefined,
    cell: ({ row: { original: r } }) => <Percent value={r.gap_percent} />,
  },
  {
    id: "history",
    header: "History",
    enableSorting: false,
    cell: ({ row: { original: r } }) => (
      <Trend values={r.sparkline} name={r.name} />
    ),
  },
  { accessorKey: "listings", header: "Listings" },
  { accessorKey: "units", header: "Units" },
  {
    id: "signal",
    accessorFn: (r) => r.signal?.crowding,
    header: "Signal",
    cell: ({ row: { original: r } }) =>
      r.signal ? (
        <Tip text={signalEvidence(r.signal)}>
          <span>
            {isSignal(r.signal.crowding) && (
              <SignalPill label={r.signal.crowding} />
            )}{" "}
            {isSignal(r.signal.overshoot.label) && (
              <SignalPill label={r.signal.overshoot.label} />
            )}
          </span>
        </Tip>
      ) : (
        "unknown"
      ),
  },
];
function CardRow({ row: r }: { row: components["schemas"]["MarketCardRow"] }) {
  return (
    <div className={styles["card-row"]}>
      <div>
        <ItemLink
          id={r.item_id}
          name={r.name}
          quality={r.quality}
          badge
          variant={identityVariant(r)}
        />
        <small>
          {r.variant_state === "base" ? (
            "base"
          ) : (
            <Identity state={r.variant_state} />
          )}
          {r.outside_chains && " · Outside our chains"}
        </small>
        <small>
          <Money copper={r.price_copper} /> now ·{" "}
          <Money copper={r.typical_copper} /> typical
        </small>
      </div>
      <div className={styles.trend}>
        <Trend values={r.sparkline} name={r.name} />
        <Percent value={r.gap_percent} />
        {r.removed_units !== null && (
          <small>{r.removed_units.toLocaleString("en-US")} units</small>
        )}
      </div>
    </div>
  );
}
export function Market({ source }: { source: string }) {
  const [role, setRole] = useState("levels"),
    [q, setQ] = useState("");
  const [sorting, setSorting] = useState<SortingState>([
    { id: "gap_percent", desc: true },
  ]);
  const [params] = useSearchParams();
  const sort = sorting[0];
  const reach = readWindow(source);
  const path =
    "market?" +
    new URLSearchParams({
      role,
      q,
      window: String(reach),
      sort: sort?.id || "gap_percent",
      descending: String(sort?.desc ?? true),
    });
  const query = useQuery<MarketData>({
    placeholderData: (previous, query) =>
      query?.queryKey[0] === source ? previous : undefined,
    queryKey: [source, "market", role, q, sorting, reach],
    queryFn: ({ signal }) => get<MarketData>(path, source, signal),
  });
  if (query.error)
    return (
      <ErrorState
        error={query.error}
        source={source}
        retry={() => {
          void query.refetch();
        }}
      />
    );
  if (!query.data) return <p role="status">Loading saved Market…</p>;
  const data = query.data;
  return (
    <>
      <PageHead
        eyebrow={
          <>
            Scan {data.evidence.scan_id || "unknown"} ·{" "}
            {data.item_count.toLocaleString("en-US")} items ·{" "}
            {data.evidence.freshness?.upstream_known
              ? `${Number(data.evidence.freshness.age_hours).toFixed(1)}h old`
              : "price age unknown"}{" "}
            · <UtcTime value={data.evidence.finished_at} />
          </>
        }
        title="Market"
        subtitle={`${data.listed_chain_count.toLocaleString("en-US")} listed now of ${data.chain_count.toLocaleString("en-US")} items in our chains. Listings are supply, not sales.`}
      />
      {(data.note || data.warning) && (
        <p role="status">
          {data.note} {data.warning}
        </p>
      )}
      <div className={styles.pulse}>
        {(["cheap", "high", "early"] as const).map((key, i) => (
          <Panel
            key={key}
            title={
              ["Cheaper than usual", "Dearer than usual", "Left early"][i]!
            }
            subtitle={key === "early" ? "last 3 gaps" : "vs typical"}
          >
            {data.cards[key]!.preview.map((r, i) => (
              <CardRow key={i} row={r} />
            ))}
            {!data.cards[key]!.preview.length && (
              <p className={styles.muted}>No qualifying evidence.</p>
            )}
            {!!data.cards[key]!.more.length && (
              <details>
                <summary>{data.cards[key]!.more.length} more</summary>
                {data.cards[key]!.more.map((r, i) => (
                  <CardRow key={i} row={r} />
                ))}
              </details>
            )}
            {key === "early" && (
              <p className={styles.muted}>
                bought or cancelled; an upper bound on sales
              </p>
            )}
          </Panel>
        ))}
      </div>
      <Panel
        title="Listed items"
        action={
          <div className={styles.tools}>
            {[
              ["levels", "For our levels"],
              ["all", "All in our chains"],
              ["materials", "Materials"],
              ["crafts", "Crafts and intermediates"],
              ["signal", "With a signal"],
            ].map(([v, label]) => (
              <button
                key={v}
                aria-pressed={role === v}
                onClick={() => setRole(v!)}
              >
                {label}
              </button>
            ))}
            <input
              aria-label="Search snapshot by name or ID"
              placeholder="Filter by name or ID"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
        }
      >
        <p className={styles.muted}>
          {role === "levels" && !q.trim()
            ? `Catalog skill-up bands from our captured ranks through the next ${reach} points (Team’s window). Unknown ranks are excluded. `
            : ""}
          {data.rows.length.toLocaleString("en-US")} items shown.
        </p>
        <DataGrid
          rows={data.rows}
          columns={
            data.reference &&
            data.rows.some(
              (r) => !r.beta_faded || r.variants.some((v) => !v.beta_faded),
            )
              ? [
                  ...columns.slice(0, 3),
                  {
                    id: "beta_typical_copper",
                    header: "Beta typical",
                    enableSorting: false,
                    cell: ({ row: { original: r } }) =>
                      r.beta_faded ? null : (
                        <Tip
                          text={`beta reference, a different market · ${data.reference!.label} · newest scan ${data.reference!.newest_scan ? `${utcLabel(data.reference!.newest_scan)} UTC` : "unknown"}`}
                        >
                          <span>
                            <BetaQuote
                              copper={r.beta_typical_copper}
                              livePrice={r.price_copper}
                              ratio={r.beta_ratio}
                            />
                          </span>
                        </Tip>
                      ),
                  },
                  ...columns.slice(3),
                ]
              : columns
          }
          subRows={(r) => r.variants as Row[]}
          rowKey={(r) => `${r.item_id}:${identityVariant(r)}`}
          onSort={setSorting}
          initialSorting={sorting}
          selected={(r) =>
            String(r.item_id) === params.get("inspect") &&
            (!params.get("variant") ||
              params.get("variant") === identityVariant(r))
          }
        />
        {!data.rows.length && !data.note && (
          <p>No items match. Clear the filter or try an item ID.</p>
        )}
      </Panel>
      <details className={styles.evidence}>
        <summary>Market evidence and scan movement</summary>
        <p>
          Lowest buyout vs earlier daily median; price cards require at least 5
          listings and 10 units per identity, with one labelled identity per
          item. Units are listed supply. Sellers unknown; no sales or demand
          forecast.
        </p>
        <Evidence
          data={{
            evidence: data.evidence,
            floods: data.floods,
            removals: data.removals,
            movement: data.movement,
          }}
        />
      </details>
    </>
  );
}
