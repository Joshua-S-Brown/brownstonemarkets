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
import { UtcTime } from "../../ui/UtcTime";
import { Tip, Sparkline, ErrorState } from "../../ui/parts";
import { DataGrid } from "../../ui/DataGrid";
import { Evidence } from "../../ui/Evidence";
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
          <Identity state={r.variant_state} />
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
  const [role, setRole] = useState("all"),
    [q, setQ] = useState("");
  const [sorting, setSorting] = useState<SortingState>([
    { id: "gap_percent", desc: true },
  ]);
  const [params] = useSearchParams();
  const sort = sorting[0];
  const path =
    "market?" +
    new URLSearchParams({
      role,
      q,
      sort: sort?.id || "gap_percent",
      descending: String(sort?.desc ?? true),
    });
  const query = useQuery<MarketData>({
    placeholderData: (previous, query) =>
      query?.queryKey[0] === source ? previous : undefined,
    queryKey: [source, "market", role, q, sorting],
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
        <DataGrid
          rows={data.rows}
          columns={columns}
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
          Lowest buyout vs earlier daily median; thin items excluded from price
          cards. Units are listed supply. Sellers unknown; no sales or demand
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
