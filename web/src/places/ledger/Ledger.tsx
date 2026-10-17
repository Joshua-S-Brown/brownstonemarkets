import { Identity } from "../../ui/Identity";
import { PageHead } from "../../ui/PageHead";
import { CharacterName } from "../../ui/CharacterName";
import type { ColumnDef } from "@tanstack/react-table";
import { lazy, Suspense, useMemo, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { get } from "../../api/client";
import type { components } from "../../api/schema";
import { DataGrid } from "../../ui/DataGrid";
import { Evidence } from "../../ui/Evidence";
import { Money } from "../../ui/Money";
import { ItemLink } from "../../ui/ItemLink";
import { ErrorState, Pill } from "../../ui/parts";
import { GoldPairs, Residuals } from "./Tables";
import { Targets } from "./Targets";
import { readDays, writeDays, type Days } from "./state";
import styles from "../../theme/app.module.css";
const Chart = lazy(() => import("./Chart").then((m) => ({ default: m.Chart })));
type Payload = components["schemas"]["Ledger"];
type Total =
  | components["schemas"]["GoldTotal"]
  | components["schemas"]["ItemTotal"];
function CategoryRow({
  source,
  kind,
  row,
  q = "",
  chains = false,
}: {
  source: string;
  kind: "gold" | "items";
  row: Total;
  q?: string;
  chains?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const query = useQuery({
    queryKey: [
      source,
      "ledger",
      "movements",
      kind,
      row.character,
      row.day,
      row.category,
      q,
      chains,
    ],
    enabled: open,
    queryFn: ({ signal }) =>
      get<components["schemas"]["Movement"][]>(
        "ledger/movements?" +
          new URLSearchParams({
            ledger: kind,
            q,
            chains: String(chains),
            name: row.character[0],
            realm: row.character[1],
            faction: row.character[2],
            day: row.day,
            category: row.category,
          }),
        source,
        signal,
      ),
  });
  return (
    <div>
      <button aria-expanded={open} onClick={() => setOpen(!open)}>
        {row.category}
      </button>{" "}
      {open && (
        <>
          {query.error && <p role="alert">{query.error.message}</p>}
          {query.data ? (
            query.data.map((m, i) => (
              <div key={i}>
                {m.item_id != null && (
                  <ItemLink
                    id={m.item_id}
                    name={m.name ?? `Item ${m.item_id}`}
                  />
                )}
                <Evidence data={m} />
              </div>
            ))
          ) : (
            <p>Loading movements…</p>
          )}
        </>
      )}
    </div>
  );
}
function CharacterLink({ character }: { character: [string, string, string] }) {
  return <CharacterName character={character} />;
}
function Totals({
  source,
  kind,
  rows,
  q = "",
  chains = false,
}: {
  source: string;
  kind: "gold" | "items";
  rows: Total[];
  q?: string;
  chains?: boolean;
}) {
  const columns = useMemo<ColumnDef<Total>[]>(
    () => [
      {
        accessorKey: "character",
        header: "Character",
        cell: ({ row: { original: r } }) => (
          <CharacterLink character={r.character} />
        ),
      },
      { accessorKey: "day", header: "UTC day" },
      {
        accessorKey: "category",
        header: "Category · open movements",
        cell: ({ row: { original: r } }) => (
          <CategoryRow
            source={source}
            kind={kind}
            row={r}
            q={q}
            chains={chains}
          />
        ),
      },
      {
        id: "in",
        accessorFn: (r) => ("in_copper" in r ? r.in_copper : r.in_units),
        header: kind === "gold" ? "Gold in" : "Units in",
        cell: ({ row: { original: r } }) =>
          "in_copper" in r ? <Money copper={r.in_copper} /> : r.in_units,
      },
      {
        id: "out",
        accessorFn: (r) => ("out_copper" in r ? r.out_copper : r.out_units),
        header: kind === "gold" ? "Gold out" : "Units out",
        cell: ({ row: { original: r } }) =>
          "out_copper" in r ? <Money copper={r.out_copper} /> : r.out_units,
      },
    ],
    [source, kind, q, chains],
  );
  return <DataGrid rows={rows} columns={columns} />;
}

export function Ledger({ source }: { source: string }) {
  const [days, setDays] = useState<Days>(() => readDays(source)),
    [q, setQ] = useState(""),
    [chains, setChains] = useState(false);
  const query = useQuery({
    queryKey: [source, "ledger", days, q, chains],
    placeholderData: keepPreviousData,
    queryFn: ({ signal }) =>
      get<Payload>(
        "ledger?" + new URLSearchParams({ days, q, chains: String(chains) }),
        source,
        signal,
      ),
  });
  const data = query.data,
    gold = data?.gold,
    items = data?.items,
    stock = data?.stock;
  return (
    <>
      <PageHead
        eyebrow="Our gold and goods"
        title="Ledger"
        subtitle="Where did our gold and goods go?"
      />
      <label>
        Days
        <select
          aria-label="Days"
          value={days}
          onChange={(e) => {
            const v = e.target.value as Days;
            writeDays(source, v);
            setDays(v);
          }}
        >
          <option value="7">Last 7 UTC days</option>
          <option value="30">Last 30 UTC days</option>
          <option value="all">All</option>
        </select>
      </label>
      {query.error && (
        <ErrorState
          source={source}
          error={query.error}
          retry={() => void query.refetch()}
        />
      )}
      {!data && !query.error && <p role="status">Loading Ledger…</p>}
      {data && (
        <>
          <div className={styles["summary-strip"]}>
            {gold && (
              <>
                <span>
                  Gold in <Money copper={gold.team.in_copper} />
                </span>
                <span>
                  Out <Money copper={gold.team.out_copper} />
                </span>
                <span>
                  Net <Money copper={gold.team.net_copper} />
                </span>
                <Pill>
                  {gold.pairs.reconciled} of {gold.pairs.total} bags pairs
                  reconcile
                </Pill>
                <Pill>{gold.pairs.unknown} unknown residuals</Pill>
              </>
            )}
            {stock && (
              <span>
                Held value <Money copper={stock.value_copper} /> at listed
                prices · {stock.excluded_prices} no-price items
              </span>
            )}
          </div>
          <h2>Gold</h2>
          {data.errors.gold && <p role="alert">{data.errors.gold}</p>}
          {gold && (
            <>
              <Pill>{gold.movement_count} recorded changes</Pill>
              <Suspense fallback={<p>Loading chart…</p>}>
                {gold.daily.length ? (
                  <Chart rows={gold.daily} />
                ) : (
                  <p>
                    No gold movements for this source and days. Import journal
                    evidence in Data.
                  </p>
                )}
              </Suspense>
              <DataGrid
                rows={gold.categories}
                columns={[
                  { accessorKey: "category", header: "Category" },
                  {
                    accessorKey: "in_copper",
                    header: "Gold in",
                    cell: (c) => <Money copper={c.getValue() as number} />,
                  },
                  {
                    accessorKey: "out_copper",
                    header: "Gold out",
                    cell: (c) => <Money copper={c.getValue() as number} />,
                  },
                ]}
              />
              <h3>Per character, UTC day and category</h3>
              <Totals source={source} kind="gold" rows={gold.totals} />
              <h3>Gold reconciliation</h3>
              <GoldPairs rows={gold.reconciliation} />
              <details>
                <summary>Gold evidence</summary>
                <Evidence data={gold.evidence} />
              </details>
              <p>
                Quests and flights have no event and remain other. Team sums
                include mail between our characters.
              </p>
            </>
          )}
          <label>
            Name or item ID
            <input value={q} onChange={(e) => setQ(e.target.value)} />
          </label>
          <label>
            <input
              type="checkbox"
              checked={chains}
              onChange={(e) => setChains(e.target.checked)}
            />
            Our catalog chains only
          </label>
          <h2>Items</h2>
          {data.errors.items && <p role="alert">{data.errors.items}</p>}
          {items && (
            <>
              <div className={styles["summary-strip"]}>
                <Pill>{items.team.in_units} team units in</Pill>
                <Pill>{items.team.out_units} team units out</Pill>
              </div>
              <Pill>{items.movement_count} recorded item changes</Pill>
              <p>
                Quests, trades and use or destruction have no event and remain
                other. Matched own mail and bank transfers are excluded from
                team totals.
              </p>
              {!items.totals.length && (
                <p>
                  No item movements for this source and filters. Import journal
                  evidence in Data.
                </p>
              )}
              <Totals
                source={source}
                kind="items"
                rows={items.totals}
                q={q}
                chains={chains}
              />
              <h3>Own-character mail</h3>
              {items.transfers.map((t, i) => (
                <div key={i}>
                  <CharacterName character={t.sender} /> →{" "}
                  <CharacterName character={t.recipient} /> ·{" "}
                  <ItemLink
                    id={t.item_id}
                    name={data.names[t.item_id] ?? `Item ${t.item_id}`}
                  />{" "}
                  · {t.units} · <Pill>{t.status}</Pill>
                  <details>
                    <summary>Mail evidence</summary>
                    <Evidence data={t} />
                  </details>
                </div>
              ))}
              <h3>Bags and bank residuals</h3>
              {items.pairs.map((p) => (
                <Pill key={p.kind}>
                  {p.kind}: {p.reconciled}/{p.total} pairs without residuals
                </Pill>
              ))}
              <Residuals rows={items.reconciliation} names={data.names} />
              <details>
                <summary>Item evidence</summary>
                <Evidence data={items.evidence} />
              </details>
            </>
          )}
          <h2>Restock</h2>
          {data.errors.stock && <p role="alert">{data.errors.stock}</p>}
          {stock && (
            <>
              <div className={styles["summary-strip"]}>
                {stock.captures.map((c, i) => (
                  <Pill key={i}>
                    {typeof c.realm === "string" &&
                    typeof c.faction === "string" ? (
                      <CharacterName
                        character={[c.character, c.realm, c.faction]}
                      />
                    ) : (
                      c.character
                    )}{" "}
                    · {c.kind} ·{" "}
                    {c.unknown ? "unknown" : `${c.age_hours?.toFixed(1)}h old`}
                    {c.empty ? " · empty" : ""}
                    {c.partial ? " · partly readable" : ""}
                    {c.excluded
                      ? ` · ${c.excluded} unreadable capture(s) excluded`
                      : ""}
                  </Pill>
                ))}
              </div>
              <div className={styles["summary-strip"]}>
                <Pill>{stock.items_held} items held</Pill>
                <span>
                  Value at listed prices <Money copper={stock.value_copper} />
                </span>
                <Pill>{stock.items_short} items short</Pill>
                <span>
                  Cost to fill within limits{" "}
                  <Money copper={stock.buy_cost_copper} />
                </span>
              </div>
              <p>
                At listed prices, not what it would sell for. Excludes{" "}
                {stock.excluded_prices} held items with no price.
              </p>
              <Pill>{stock.scan_state}</Pill>
              <Targets
                source={source}
                entries={stock.entries}
                names={stock.names}
              />
              {!stock.captures.length && (
                <p>
                  No character captures for this source and market. Import bags
                  and bank snapshots in Data.
                </p>
              )}
              <DataGrid
                rows={stock.rows}
                columns={[
                  {
                    accessorKey: "name",
                    header: "Item",
                    cell: ({ row: { original: r } }) => (
                      <>
                        <ItemLink
                          id={r.item_id}
                          name={r.name.replace(
                            / \(identity (?:unresolved|variant)[^)]*\)$/,
                            "",
                          )}
                          variant={JSON.stringify([
                            r.variant_state,
                            r.variant_id,
                          ])}
                        />
                        <Identity state={r.variant_state} />
                      </>
                    ),
                  },
                  ...[
                    "held",
                    "target_units",
                    "short",
                    "buy_units",
                    "wait_units",
                    "unlisted_units",
                  ].map((k) => ({
                    accessorKey: k,
                    header: (
                      {
                        held: "Held",
                        target_units: "Target",
                        short: "Short",
                        buy_units: "Buy now",
                        wait_units: "Wait",
                        unlisted_units: "Unlisted units",
                      } as Record<string, string>
                    )[k],
                    cell: ({
                      row: { original: r },
                    }: {
                      row: { original: components["schemas"]["StockRow"] };
                    }) => (
                      <>
                        {k === "short" && r.short != null && r.at_most
                          ? "at most "
                          : ""}
                        {r[k as "held"] ?? "—"}
                      </>
                    ),
                  })),
                  ...[
                    "buy_cost_copper",
                    "fill_cost_copper",
                    "value_copper",
                  ].map((k) => ({
                    accessorKey: k,
                    header: (
                      {
                        buy_cost_copper: "Buy cost",
                        fill_cost_copper: "Fill cost",
                        value_copper: "Value",
                      } as Record<string, string>
                    )[k],
                    cell: ({
                      row: { original: r },
                    }: {
                      row: { original: components["schemas"]["StockRow"] };
                    }) =>
                      k === "fill_cost_copper" &&
                      r.fill_state === "insufficient listings" ? (
                        <>insufficient listings</>
                      ) : k === "value_copper" && r.value_copper == null ? (
                        <>no price</>
                      ) : (
                        <Money copper={r[k as "value_copper"] ?? null} />
                      ),
                  })),
                  {
                    id: "evidence",
                    header: "Evidence",
                    cell: ({ row: { original: r } }) => (
                      <details>
                        <summary>Target and purchase evidence</summary>
                        {r.limit_unknown && (
                          <Pill tone="warn">
                            Market value missing · buy limit unknown · wait
                          </Pill>
                        )}
                        <Evidence data={r} />
                      </details>
                    ),
                  },
                ]}
              />
              <p>
                Short items first. Unlisted units have no fill price. Costs buy
                whole stacks; surplus is included.
              </p>
              <details>
                <summary>Holdings by character and location</summary>
                <Evidence data={{ holdings: stock.holdings }} />
              </details>
              <details>
                <summary>Stock evidence</summary>
                <p>
                  Cautious value uses the lower positive minimum buyout / market
                  value. Missing or zero prices are excluded. Unknown locations
                  make shortfalls at most; no Today plan changes.
                </p>
                <Evidence data={stock.evidence} />
                <Evidence data={{ captures: stock.captures }} />
              </details>
            </>
          )}
        </>
      )}
      {data && (
        <details>
          <summary>Ledger evidence</summary>
          <Evidence data={data.evidence} />
        </details>
      )}
    </>
  );
}
