import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ResponsiveContainer,
  ComposedChart,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import type { ColumnDef } from "@tanstack/react-table";
import { get } from "../api/client";
import type { History, Ladder } from "../api/market";
import { DataGrid } from "../ui/DataGrid";
import { Money, moneyText } from "../ui/Money";
import { ErrorState } from "../ui/parts";
import { Evidence } from "../ui/Evidence";
export const scanLabel = (time: string) =>
  `${new Date(time).toISOString()} UTC · ${new Date(time).toLocaleString()} local`;
export function historyData(history: History) {
  return history.points.map((p) => ({
    time: Date.parse(p.finished_at),
    lowest: p.metrics?.min_buyout ?? null,
    p25: p.metrics?.market_value ?? null,
    units: p.metrics?.units ?? null,
    scan: p.scan_id,
  }));
}
const columns: ColumnDef<Ladder["rows"][number]>[] = [
  {
    accessorKey: "price_copper",
    header: "Unit price",
    cell: ({ row }) => <Money copper={row.original.price_copper} />,
  },
  { accessorKey: "listings", header: "Listings" },
  { accessorKey: "units", header: "Units" },
  { accessorKey: "cumulative_units", header: "Cumulative units" },
];
export function LadderPanel({
  source,
  id,
  scan,
}: {
  source: string;
  id: number;
  scan: string;
}) {
  const query = useQuery({
    queryKey: [source, "ladder", id, scan],
    queryFn: ({ signal }) =>
      get<Ladder>(
        `items/${id}/ladder?scan=${encodeURIComponent(scan)}`,
        source,
        signal,
      ),
  });
  const [zoom, setZoom] = useState<number | null>(null);
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
  if (!query.data) return <p role="status">Loading listing ladder…</p>;
  const l = query.data,
    end = zoom ?? l.zoom_copper,
    rows = l.rows;
  return (
    <>
      <p>
        {rows.reduce((n, r) => n + r.listings, 0).toLocaleString()} buyout
        listings · {rows.reduce((n, r) => n + r.units, 0).toLocaleString()}{" "}
        units · {rows.length} price levels
      </p>
      <p>
        Without a buyout: {l.no_buyout_listings} listings · {l.no_buyout_units}{" "}
        units (excluded from prices)
      </p>
      <p>
        {l.freshness.stale ? "Stale" : "Saved scan"} ·{" "}
        {Number(l.freshness.age_hours).toFixed(1)} hours since scan
      </p>
      {l.note && <p>{l.note} Choose another scan.</p>}
      {rows.length > 0 && (
        <>
          <p>
            Zoomed to the cheapest 95% of units; use the slider for higher asks.
            The table includes every level.
          </p>
          <label>
            Highest displayed ask <Money copper={end} />
            <input
              aria-label="Highest displayed ask"
              type="range"
              min={rows[0]!.price_copper}
              max={rows.at(-1)!.price_copper}
              value={end ?? 0}
              onChange={(e) => setZoom(Number(e.target.value))}
            />
          </label>
          <div style={{ height: 300, width: "100%" }}>
            <ResponsiveContainer>
              <LineChart
                data={rows.filter((r) => r.price_copper <= (end ?? Infinity))}
                margin={{ left: 5, right: 15, bottom: 30 }}
              >
                <CartesianGrid stroke="var(--line)" />
                <XAxis
                  dataKey="price_copper"
                  type="number"
                  domain={["dataMin", "dataMax"]}
                  tickFormatter={moneyText}
                  label={{ value: "Unit buyout", position: "bottom" }}
                />
                <YAxis dataKey="cumulative_units" />
                <Tooltip
                  content={({ active, payload }) => {
                    const r = payload?.[0]?.payload;
                    return active && r ? (
                      <div
                        style={{
                          background: "var(--surface)",
                          border: "1px solid var(--line)",
                          padding: 12,
                        }}
                      >
                        <Money copper={r.price_copper} /> / unit
                        <br />
                        {r.listings} listings · {r.units} units
                        <br />
                        {r.cumulative_units} cumulative units
                      </div>
                    ) : null;
                  }}
                />
                <Line
                  type="stepAfter"
                  dataKey="cumulative_units"
                  name="Cumulative units"
                  stroke="var(--accent)"
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <DataGrid rows={rows} columns={columns} />
        </>
      )}
      {rows.length === 0 && !l.note && (
        <p>No buyout prices to chart. Choose another scan.</p>
      )}
    </>
  );
}
export function ItemCharts({
  source,
  id,
  listings = false,
}: {
  source: string;
  id: number;
  listings?: boolean;
}) {
  const [scan, setScan] = useState("");
  const query = useQuery({
    queryKey: [source, "history", id],
    queryFn: ({ signal }) =>
      get<History>(`items/${id}/history`, source, signal),
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
  if (!query.data) return <p role="status">Loading price history…</p>;
  const h = query.data;
  return (
    <>
      <p>
        {h.points.length} eligible scans · Base/compatible legacy history only.{" "}
        {h.other_identities} other newest identities excluded.
      </p>
      {h.note && <p>{h.note}</p>}
      {!listings && (
        <>
          {h.points.filter((p) => p.metrics).length < 2 && (
            <p>
              More scans with compatible item evidence are needed for a trend.
            </p>
          )}
          <div style={{ width: "100%", height: 340 }}>
            <ResponsiveContainer>
              <ComposedChart
                data={historyData(h)}
                margin={{ left: 5, right: 5, bottom: 35 }}
              >
                <CartesianGrid stroke="var(--line)" />
                <XAxis
                  dataKey="time"
                  type="number"
                  domain={["dataMin", "dataMax"]}
                  scale="time"
                  tickFormatter={(v) => new Date(v).toLocaleDateString()}
                />
                <YAxis yAxisId="price" tickFormatter={moneyText} width={85} />
                <YAxis yAxisId="supply" orientation="right" width={45} />
                <Tooltip
                  labelFormatter={(v, p) =>
                    `Scan ${p[0]?.payload.scan ?? ""} · ${scanLabel(new Date(Number(v)).toISOString())}`
                  }
                  formatter={(v, name) => [
                    name === "Units listed" ? String(v) : moneyText(Number(v)),
                    name,
                  ]}
                />
                <Line
                  yAxisId="price"
                  dataKey="lowest"
                  name="Lowest unit buyout"
                  connectNulls={false}
                  stroke="var(--accent)"
                />
                <Line
                  yAxisId="price"
                  dataKey="p25"
                  name="Market value (p25)"
                  connectNulls={false}
                  stroke="var(--gold)"
                />
                <Line
                  yAxisId="supply"
                  dataKey="units"
                  name="Units listed"
                  connectNulls={false}
                  stroke="var(--muted)"
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <p>
            Lowest unit buyout · Market value (p25) · Units listed (right axis)
          </p>
        </>
      )}
      {listings && h.scans.length > 0 && (
        <>
          <label>
            Ladder scan
            <select
              aria-label="Ladder scan"
              value={scan || h.scans[0]!.scan_id}
              onChange={(e) => setScan(e.target.value)}
            >
              {h.scans.map((s) => (
                <option key={s.scan_id} value={s.scan_id}>
                  {scanLabel(s.finished_at)}
                </option>
              ))}
            </select>
          </label>
          <LadderPanel
            key={scan}
            source={source}
            id={id}
            scan={scan || h.scans[0]!.scan_id}
          />
        </>
      )}
      <p>Units listed are supply, never sales, demand or volume.</p>
      {!listings && <RemovalHistory h={h} />}
    </>
  );
}

export function RemovalHistory({ h }: { h: History }) {
  const pairs = h.removals?.pairs?.filter((p) => !p.skipped) ?? [];
  const [all, setAll] = useState(false);
  return (
    <section>
      <h2>Removed between scans</h2>
      <p>Removed early is an upper bound on purchases: bought or cancelled.</p>
      {h.removals_error && <p role="alert">{h.removals_error}</p>}
      <p>{h.removals?.note}</p>
      <p>
        {(h.removals?.pairs?.length ?? 0) - pairs.length} skipped gaps (over 12
        hours)
      </p>
      {(all ? pairs : pairs.slice(0, 3)).map((p, i) => (
        <section key={i}>
          <h3>
            {scanLabel(p.earlier.finished_at)} →{" "}
            {scanLabel(p.later.finished_at)}
          </h3>
          <p>Gap {(p.gap / 3600).toFixed(2)} hours</p>
          {p.items.map((r, j) => (
            <section key={j}>
              <p>
                {r.variant_state || "legacy"} {r.variant_id}
              </p>
              {(["early", "expiry", "unknown"] as const).map((k, i) => (
                <p key={k}>
                  {
                    [
                      "Removed early",
                      "Could have expired",
                      "Time left unknown",
                    ][i]
                  }
                  : {r[k].listings} listings · {r[k].units} units
                </p>
              ))}
              <p>
                Listings without a buyout (excluded): earlier{" "}
                {r.without_buyout.earlier} · later {r.without_buyout.later}
              </p>
              <details>
                <summary>Matching evidence</summary>
                <Evidence data={{ listings: r.evidence }} />
              </details>
            </section>
          ))}
        </section>
      ))}
      {pairs.length > 3 && (
        <button onClick={() => setAll(!all)}>
          {all ? "Show three gaps" : "Show all scan gaps"}
        </button>
      )}
    </section>
  );
}
