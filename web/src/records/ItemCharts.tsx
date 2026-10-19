import { UtcTime, utcLabel } from "../ui/UtcTime";
import { Identity } from "../ui/Identity";
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
  Bar,
  Legend,
  ReferenceLine,
} from "recharts";
import type { ColumnDef } from "@tanstack/react-table";
import { get } from "../api/client";
import type { History, Ladder, Removal } from "../api/market";
import { DataGrid } from "../ui/DataGrid";
import { Money, moneyText } from "../ui/Money";
import { ErrorState } from "../ui/parts";
import { Evidence } from "../ui/Evidence";
export const scanLabel = (time: string) => `${utcLabel(time)} UTC`;
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
  overview = false,
  typical = null,
}: {
  source: string;
  id: number;
  listings?: boolean;
  overview?: boolean;
  typical?: number | null;
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
      {!overview && (
        <p>
          {h.points.length} eligible scans · Base/compatible legacy history
          only. {h.other_identities} other newest identities excluded.
        </p>
      )}
      {h.note && <p>{h.note}</p>}
      {!listings && (
        <>
          {h.points.filter((p) => p.metrics).length < 2 && (
            <p>
              More scans with compatible item evidence are needed for a trend.
            </p>
          )}
          <div style={{ width: "100%", height: overview ? 220 : 340 }}>
            <ResponsiveContainer>
              <ComposedChart
                data={historyData(h)}
                margin={{ left: 5, right: 25, bottom: 35 }}
              >
                <CartesianGrid stroke="var(--line)" />
                <XAxis
                  dataKey="time"
                  type="number"
                  domain={["dataMin", "dataMax"]}
                  scale="time"
                  tickFormatter={(v) => utcLabel(new Date(v).toISOString())}
                />
                <YAxis
                  yAxisId="price"
                  tickFormatter={moneyText}
                  width={70}
                  label={{
                    value: "Unit price",
                    angle: -90,
                    position: "insideLeft",
                  }}
                />
                <YAxis
                  yAxisId="supply"
                  orientation="right"
                  width={45}
                  label={{
                    value: "Units listed",
                    angle: 90,
                    position: "right",
                    offset: 8,
                  }}
                />
                <Legend />
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
                {!overview && (
                  <Line
                    yAxisId="price"
                    dataKey="p25"
                    name="Market value (p25)"
                    connectNulls={false}
                    stroke="var(--chart-2)"
                  />
                )}
                {overview && typical !== null && (
                  <ReferenceLine
                    yAxisId="price"
                    y={typical}
                    ifOverflow="extendDomain"
                    stroke="var(--chart-2)"
                    strokeDasharray="5 4"
                    label="Typical"
                  />
                )}
                <Bar
                  yAxisId="supply"
                  dataKey="units"
                  name="Units listed"
                  fill="var(--chart-3)"
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <p>
            {overview
              ? "Stored scan prices · dashed reference: typical earlier price"
              : "Lowest unit buyout · Market value (p25) · Units listed (right axis)"}
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
      {!listings && !overview && <RemovalHistory h={h} />}
    </>
  );
}

const kinds = ["early", "expiry"] as const;
type Kind = (typeof kinds)[number];
export function RemovalHistory({ h }: { h: History }) {
  const pairs = h.removals?.pairs?.filter((p) => !p.skipped) ?? [];
  const totals = new Map<string, Pick<Removal, "variant_state" | Kind>>();
  pairs.forEach((p) =>
    p.items.forEach((r) => {
      const key = JSON.stringify([r.variant_state, r.variant_id]);
      const t = totals.get(key) ?? {
        variant_state: r.variant_state,
        early: { listings: 0, units: 0 },
        expiry: { listings: 0, units: 0 },
      };
      kinds.forEach((k) => {
        t[k] = {
          listings: t[k].listings + r[k].listings,
          units: t[k].units + r[k].units,
        };
      });
      totals.set(key, t);
    }),
  );
  return (
    <section>
      <h2>Removed between scans</h2>
      <p>Removed early is an upper bound on purchases: bought or cancelled.</p>
      {h.removals_error && <p role="alert">{h.removals_error}</p>}
      <p>{h.removals?.note}</p>
      <p>
        {pairs.length} comparable gaps ·{" "}
        {(h.removals?.pairs?.length ?? 0) - pairs.length} skipped gaps (over 12
        hours)
      </p>
      {[...totals.values()].map((t, i) => (
        <p key={i}>
          <Identity state={t.variant_state} several={totals.size > 1} /> Removed
          early: {t.early.listings.toLocaleString("en-US")} listings ·{" "}
          {t.early.units.toLocaleString("en-US")} units · Could have expired:{" "}
          {t.expiry.listings.toLocaleString("en-US")} listings ·{" "}
          {t.expiry.units.toLocaleString("en-US")} units
        </p>
      ))}
      {pairs.map((p, i) => (
        <details key={i}>
          <summary>
            <UtcTime value={p.earlier.finished_at} /> →{" "}
            <UtcTime value={p.later.finished_at} /> · gap{" "}
            {(p.gap / 3600).toFixed(2)} hours
          </summary>
          {p.items.map((r, j) => (
            <section key={j}>
              <p>
                <Identity
                  state={r.variant_state}
                  several={p.items.length > 1}
                />
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
        </details>
      ))}
    </section>
  );
}
