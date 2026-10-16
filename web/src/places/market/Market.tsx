import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import type { ColumnDef } from "@tanstack/react-table";
import { get } from "../../api/client";
import type { Market as MarketData, Row, Signal } from "../../api/market";
import { Money } from "../../ui/Money";
import { ItemLink } from "../../ui/ItemLink";
import { Pill, Tip, Sparkline, ErrorState } from "../../ui/parts";
import { DataGrid } from "../../ui/DataGrid";
import { Evidence } from "../../ui/Evidence";
import styles from "../../theme/app.module.css";
export function signalEvidence(s: Signal) {
  return `${s.listings} listings · ${s.units} units · largest stack ${s.largest_stack_units}/${s.units} · lowest buyout changes ${s.churn.changed}/${s.churn.pairs} comparable gaps${s.churn.pairs ? "" : " (churn unknown)"} · ${s.overshoot.days} days, ${s.overshoot.scans} scans · ${s.overshoot.label}`;
}
export function identityVariant(row: {
  variant_state: string | null;
  variant_id: string | null;
}) {
  return JSON.stringify([row.variant_state, row.variant_id]);
}
/** Distinct catalog items in the newest snapshot; chain items without listings have no row. */
export function chainListed(rows: Row[]) {
  return new Set(rows.filter((r) => r.roles.length > 0).map((r) => r.item_id))
    .size;
}
export function filterRows(rows: Row[], role: string, q: string) {
  const search = q.trim().toLowerCase();
  return rows.filter((r) =>
    search
      ? r.name.toLowerCase().includes(search) ||
        String(r.item_id).includes(search)
      : role === "signal"
        ? r.roles.length > 0 &&
          !!r.signal &&
          (r.signal.crowding === "contested" ||
            ["cheap", "high"].includes(r.signal.overshoot.label))
        : role === "all"
          ? r.roles.length > 0
          : r.roles.includes(role),
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
          variant={identityVariant(r)}
        />
        <small>
          {r.item_id} · {r.variant_state || "legacy"} {r.variant_id}
        </small>
      </>
    ),
  },
  ...(["price_copper", "typical_copper", "gap_copper"] as const).map(
    (key, i) => ({
      id: key,
      accessorFn: (r: Row) => r[key] ?? undefined,
      sortDescFirst: false,
      header: ["Lowest / unit", "Typical / unit", "Gap to typical"][i],
      sortUndefined: "last" as const,
      cell: ({ row: { original: r } }: { row: { original: Row } }) => (
        <>
          <Money copper={r[key]} />
          {key === "gap_copper" && r.gap_percent !== null && (
            <small>{r.gap_percent.toFixed(1)}%</small>
          )}
        </>
      ),
    }),
  ),
  {
    id: "history",
    header: "Stored lowest",
    enableSorting: false,
    cell: ({ row: { original: r } }) => (
      <Sparkline
        values={r.sparkline}
        label={`${r.name} stored lowest buyout`}
      />
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
          <Pill>
            {r.signal.crowding} · {r.signal.overshoot.label}
          </Pill>
        </Tip>
      ) : (
        "unknown"
      ),
  },
];
export function Market({ source }: { source: string }) {
  const [role, setRole] = useState("all"),
    [q, setQ] = useState("");
  const [params] = useSearchParams();
  const query = useQuery({
    queryKey: [source, "market"],
    queryFn: ({ signal }) => get<MarketData>("market", source, signal),
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
  const data = query.data,
    rows = filterRows(data.rows, role, q);
  return (
    <>
      <p className={styles.eyebrow}>Your saved market</p>
      <h1>Market</h1>
      <p className={styles.muted}>
        What is the market telling me? ·{" "}
        {chainListed(data.rows).toLocaleString("en-US")} listed now of{" "}
        {data.chain_count.toLocaleString("en-US")} items in our chains
      </p>
      <div className={styles.pulse}>
        {(["cheap", "high", "early"] as const).map((key, i) => (
          <section key={key}>
            <h2>
              {["Cheaper than usual", "Dearer than usual", "Left early"][i]}
            </h2>
            <p className={styles.muted}>
              {key === "early"
                ? "Removed early units · upper bound on purchases"
                : "Lowest buyout vs earlier daily median · thin items excluded"}
            </p>
            {data.pulse[key].length === 0 && <p>No qualifying evidence.</p>}
            {data.pulse[key].map((r, i) => (
              <div key={i}>
                <ItemLink
                  id={r.item_id}
                  name={r.item_name}
                  variant={identityVariant(r)}
                />
                <small>
                  {r.variant_state || "legacy"} {r.variant_id} ·{" "}
                  {"early" in r
                    ? `${r.early.units} units`
                    : r.overshoot.ratio
                      ? `${(100 * (r.overshoot.ratio.numerator / r.overshoot.ratio.denominator - 1)).toFixed(1)}% · ${r.overshoot.days} days, ${r.overshoot.scans} scans`
                      : "unknown"}
                </small>
              </div>
            ))}
          </section>
        ))}
      </div>
      <p>
        {data.note}
        {data.warning}
      </p>
      <div className={styles["grid-tools"]} aria-label="Catalog role filters">
        {[
          ["all", "All in our chains"],
          ["materials", "Materials"],
          ["crafts", "Crafts"],
          ["intermediates", "Intermediates"],
          ["signal", "With a signal"],
        ].map(([v, label]) => (
          <button key={v} aria-pressed={role === v} onClick={() => setRole(v!)}>
            {label}
          </button>
        ))}
        <input
          aria-label="Search snapshot by name or ID"
          placeholder="Search every snapshot item…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>
      <DataGrid
        rows={rows}
        columns={columns}
        selected={(r) =>
          String(r.item_id) === params.get("inspect") &&
          (!params.get("variant") ||
            params.get("variant") === identityVariant(r))
        }
      />
      <p className={styles.muted}>
        Units are listed supply. Sellers unknown; no sales or demand forecast.
      </p>
      <details>
        <summary>Market evidence and scan movement</summary>
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
