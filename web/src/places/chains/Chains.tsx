import { PageHead } from "../../ui/PageHead";
import { Panel } from "../../ui/Panel";
import { Pill, Tip } from "../../ui/parts";
import { UtcTime } from "../../ui/UtcTime";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import type { components } from "../../api/schema";
import { get } from "../../api/client";
import { Money } from "../../ui/Money";
import { ItemLink } from "../../ui/ItemLink";
import { addToTonight } from "../today/state";
import styles from "./chains.module.css";
import appStyles from "../../theme/app.module.css";
type Outputs = components["schemas"]["Outputs"];
const METHOD: Record<string, string> = {
  buy: "Buy",
  vendor: "Vendor",
  craft: "Craft",
  missing: "No route",
};
export type Route = components["schemas"]["Route"];
export function Chains({ source }: { source: string }) {
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState("");
  const catalog = params.get("catalog") || "",
    recipe = params.get("recipe") || "";
  const query = useQuery({
    queryKey: [source, "chains", q],
    queryFn: ({ signal }) =>
      get<Outputs>("chains?q=" + encodeURIComponent(q), source, signal),
  });
  const choose = (row: Outputs["hits"][number]) => {
    setParams((p) => {
      p.set("catalog", row.catalog_id);
      p.set("recipe", String(row.recipe_id));
      return p;
    });
  };
  const first = query.data?.ranked[0];
  // The projection puts makeable crafts first, retaining Board order in each group.
  useEffect(() => {
    if (catalog || !first) return;
    setParams(
      (p) => {
        p.set("catalog", first.catalog_id);
        p.set("recipe", String(first.recipe_id));
        return p;
      },
      { replace: true },
    );
  }, [catalog, first, setParams]);
  return (
    <div className={styles.page}>
      <PageHead
        eyebrow={
          <>
            Recipe routes · Cautious basis ·{" "}
            <UtcTime value={query.data?.scan_at} />
          </>
        }
        title="Supply chains"
        subtitle="Where does the margin come from?"
      />
      <p className={styles.muted}>
        Forcing is exploration only: Today still costs with the cheapest routes.
      </p>
      {query.error && <p role="alert">{query.error.message}</p>}
      <div className={styles.picker}>
        <nav className={styles.chips} aria-label="Top ranked crafts">
          {query.data?.ranked.map((r) => (
            <div className={styles.chip} key={r.catalog_id + r.recipe_id}>
              <button
                aria-pressed={
                  catalog === r.catalog_id && recipe === String(r.recipe_id)
                }
                onClick={() => choose(r)}
              >
                {r.name} · {r.profession}
              </button>
              {!r.makeable && (
                <Tip text={r.team_reason}>
                  <Pill tone="warn">no one on the team can make this yet</Pill>
                </Tip>
              )}
            </div>
          ))}
        </nav>
        <label className={styles.search}>
          Find an output by name or item ID
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Name or item ID"
          />
        </label>
      </div>
      {first && !first.makeable && (
        <p className={styles.muted}>
          No ranked craft is makeable by the team tonight. Opening the first
          ranked craft; inspect team status for the next step.
        </p>
      )}
      {q && query.data && (
        <div aria-label="Search results">
          {query.data.hits.map((r) => (
            <button key={r.catalog_id + r.recipe_id} onClick={() => choose(r)}>
              {r.name} · {r.profession} · {r.item_id}
            </button>
          ))}
          <p>
            {query.data.hit_count > query.data.hits.length
              ? `Showing ${query.data.hits.length} of ${query.data.hit_count}; narrow the search.`
              : !query.data.hit_count && "No compatible recipe matches."}
          </p>
        </div>
      )}
      {catalog && recipe ? (
        <ChainRoute
          key={`${source}:${catalog}:${recipe}`}
          source={source}
          catalog={catalog}
          recipe={recipe}
        />
      ) : (
        <p>Choose an output to follow its materials.</p>
      )}
    </div>
  );
}
function ChainRoute({
  source,
  catalog,
  recipe,
}: {
  source: string;
  catalog: string;
  recipe: string;
}) {
  const [forced, setForced] = useState<Record<number, string>>({}),
    [batch, setBatch] = useState(1);
  const client = useQueryClient();
  const args = new URLSearchParams({
    catalog_id: catalog,
    recipe_id: recipe,
    batch: String(batch),
  });
  Object.entries(forced).forEach(([id, method]) =>
    args.append("force", `${id}:${method}`),
  );
  const query = useQuery({
    queryKey: [source, "chains", catalog, recipe, batch, forced],
    placeholderData: keepPreviousData,
    queryFn: ({ signal }) => get<Route>("chains/route?" + args, source, signal),
  });
  const add = useMutation({
    mutationFn: () =>
      addToTonight(
        source,
        { catalog_id: catalog, recipe_id: Number(recipe), batch_size: batch },
        client,
      ),
  });
  const force = (id: number, method?: string) =>
    setForced((old) => {
      const next = { ...old };
      if (method) next[id] = method;
      else delete next[id];
      return next;
    });
  const r = query.data;
  return (
    <section aria-label="Selected route">
      {query.error && <p role="alert">{query.error.message}</p>}
      {!r ? (
        <p role="status">Loading route…</p>
      ) : (
        <>
          {r.reason && <p>{r.reason}</p>}
          {query.isFetching && (
            <p className={styles.muted} role="status">
              Recalculating…
            </p>
          )}
          <div className={styles.layout}>
            <Panel
              title="Route"
              subtitle={r.name}
              evidence={{ ...r.evidence, source: r.source_evidence }}
            >
              <Graph route={r} force={force} />
            </Panel>
            <aside className={styles.side}>
              <Panel title="Per craft">
                <Waterfall route={r} />
              </Panel>
              <Panel
                title="Batch"
                subtitle={
                  <Tip
                    text={
                      "Listing depth is display only; these counts do not claim listings cover this batch. Held units never lower costs. " +
                      r.leaves
                        .map(
                          (leaf) =>
                            `${leaf.name}: ${leaf.quantity}, ${leaf.depth}`,
                        )
                        .join("; ")
                    }
                  >
                    <span className={appStyles["sr-only"]}>Batch evidence</span>
                    ⓘ
                  </Tip>
                }
                action={<strong className={styles.batch}>{batch}</strong>}
              >
                <input
                  aria-label="Crafts"
                  type="range"
                  min={1}
                  max={r.max_crafts}
                  value={batch}
                  onChange={(e) => setBatch(Number(e.target.value))}
                />
                <dl className={styles.totals}>
                  {r.leaves.map((leaf) => (
                    <div key={leaf.item_id}>
                      <dt>
                        <ItemLink id={leaf.item_id} name={leaf.name} />
                      </dt>
                      <dd>{leaf.quantity}</dd>
                    </div>
                  ))}
                  <div>
                    <dt>Spend</dt>
                    <dd>
                      <Money copper={r.spend_copper} />
                    </dd>
                  </div>
                  {r.can_add && (
                    <div>
                      <dt>Profit</dt>
                      <dd>
                        <Money copper={r.profit_copper} />
                      </dd>
                    </div>
                  )}
                </dl>
                <button
                  className={`${appStyles.primary} ${styles.add}`}
                  disabled={!r.can_add || add.isPending}
                  title={r.reason}
                  onClick={() => add.mutate()}
                >
                  Add to tonight
                </button>
                {add.data && (
                  <p role="status">
                    {add.data.reason ||
                      `Added ${add.data.batch_size} × ${r.name} to tonight`}{" "}
                    ·{" "}
                    <a href={"/app/today?" + new URLSearchParams({ source })}>
                      Open Today
                    </a>
                  </p>
                )}
                {add.error && <p role="alert">{add.error.message}</p>}
              </Panel>
            </aside>
          </div>
        </>
      )}
    </section>
  );
}
export function Graph({
  route,
  force,
}: {
  route: Route;
  force: (id: number, method?: string) => void;
}) {
  const max = Math.max(0, ...route.nodes.map((n) => n.column));
  const graph = useRef<HTMLDivElement>(null);
  const [positions, setPositions] = useState<
    Record<number, { x: number; y: number; w: number; h: number }>
  >({});
  useLayoutEffect(() => {
    const el = graph.current!;
    const measure = () => {
      const box = el.getBoundingClientRect();
      const next: typeof positions = {};
      el.querySelectorAll<HTMLElement>("[data-node]").forEach((node) => {
        const rect = node.getBoundingClientRect();
        next[Number(node.dataset.node)] = {
          x: rect.left - box.left,
          y: rect.top - box.top,
          w: rect.width,
          h: rect.height,
        };
      });
      setPositions(next);
    };
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    el.querySelectorAll("[data-node]").forEach((node) =>
      observer.observe(node),
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [route]);
  const counts = route.nodes.reduce<Record<number, number>>((counts, n) => {
    counts[n.column] = (counts[n.column] || 0) + 1;
    return counts;
  }, {});
  const rows = Math.max(1, ...Object.values(counts));
  const seen: Record<number, number> = {};
  return (
    <div className={styles.graphWrap} aria-label="Recipe graph">
      <div
        ref={graph}
        className={styles.graph}
        style={{ "--columns": max + 1 } as React.CSSProperties}
      >
        <svg
          className={styles.edges}
          width="100%"
          height="100%"
          aria-label="Input quantities"
        >
          {route.edges.map((e) => {
            const parent = positions[e.parent],
              child = positions[e.child];
            if (!parent || !child) return null;
            const x1 = child.x + child.w,
              y1 = child.y + child.h / 2,
              x2 = parent.x,
              y2 = parent.y + parent.h / 2,
              middle = (x1 + x2) / 2;
            return (
              <g key={e.parent + ":" + e.child}>
                <path
                  data-chosen={e.chosen}
                  d={`M${x1},${y1} C${middle},${y1} ${middle},${y2} ${x2},${y2}`}
                  fill="none"
                  stroke="currentColor"
                  strokeDasharray={e.chosen ? undefined : "3 5"}
                />
                <text x={middle} y={(y1 + y2) / 2 - 6} textAnchor="middle">
                  ×{e.quantity}
                </text>
              </g>
            );
          })}
        </svg>
        <ol
          className={styles.nodes}
          aria-label="Route from output to materials"
        >
          {route.nodes.map((n) => {
            const row = (seen[n.column] || 0) + 1;
            seen[n.column] = row;
            const status =
              n.characters
                .map(
                  (c) =>
                    `${c.character[0]}: ${c.craft_status}${c.character_reason ? " · " + c.character_reason : ""}`,
                )
                .join("; ") || "No character recipe evidence for this source";
            return (
              <li
                key={n.item_id}
                data-node={n.item_id}
                data-output={n.output}
                className={styles.node}
                style={{
                  gridColumn: max - n.column + 1,
                  gridRow: counts[n.column] === 1 ? `1 / span ${rows}` : row,
                }}
              >
                <h3>
                  <ItemLink id={n.item_id} name={n.name} quality={n.quality} />
                </h3>
                <p className={styles.price}>
                  <span>{n.output ? "Sells at" : "Unit cost"}</span>
                  <Money
                    copper={n.output ? n.sale_price_copper : n.unit_cost_copper}
                  />
                </p>
                {n.output ? (
                  <Pill>Output</Pill>
                ) : n.options.length >= 2 && n.units > 0 ? (
                  <div
                    className={styles.toggle}
                    role="group"
                    aria-label={`${n.name} route`}
                  >
                    {n.options.map((o) => (
                      <button
                        key={o.method}
                        aria-pressed={n.method === o.method}
                        onClick={() => force(n.item_id, o.method)}
                      >
                        {METHOD[o.method] ?? o.method}{" "}
                        <Money copper={o.unit_cost_copper} />
                      </button>
                    ))}
                  </div>
                ) : (
                  <p>
                    {n.units === 0
                      ? "Not on the chosen route"
                      : n.method === "vendor"
                        ? "Vendor"
                        : `Auction House · ${n.listings == null ? "listings unknown" : `${n.listings} listings`}`}
                  </p>
                )}
                {n.forced && (
                  <div>
                    <span>forced</span> ·{" "}
                    <button onClick={() => force(n.item_id)}>
                      Reset to cheapest
                    </button>
                  </div>
                )}
                {(n.output ||
                  n.options.some((o) => o.method === "craft") ||
                  n.route_note) && (
                  <div className={styles.status}>
                    <span>{n.maker}</span>
                    <Tip
                      text={`${status}${n.route_note ? "; " + n.route_note : ""}; ${n.units ? `${n.units} units per output craft` : "not on the chosen route"}`}
                    >
                      <span className={appStyles["sr-only"]}>
                        Team recipe status for {n.name}
                      </span>
                      ⓘ
                    </Tip>
                  </div>
                )}
                <p className={styles.muted}>
                  {n.held == null
                    ? "Held: unknown"
                    : n.held === 0
                      ? n.at_least
                        ? "None seen in captured bags and banks"
                        : "None held"
                      : `Held: ${n.at_least ? "at least " : ""}${n.held}`}
                </p>
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}

export function Waterfall({ route }: { route: Route }) {
  // Intermediates have no Sale row: scale to their largest cost instead.
  const sale = Math.max(
    1,
    route.waterfall.find((l) => l.label.startsWith("Sale"))?.amount_copper ??
      Math.max(
        0,
        ...route.waterfall.map((l) => Math.abs(l.amount_copper ?? 0)),
      ),
  );
  return (
    <div className={styles.waterfall} aria-label="Per craft copper waterfall">
      {route.waterfall.map((line, i) => (
        <div
          key={i}
          className={`${styles.waterRow} ${line.label === "Profit" ? styles.total : ""}`}
          data-negative={(line.amount_copper ?? 0) < 0}
        >
          <div className={styles.waterLabel}>
            <span>
              {line.label}
              {line.quantity != null && (
                <small className={styles.unitCost}>
                  {" "}
                  · {line.quantity} ×{" "}
                  <Money copper={line.unit_cost_copper ?? null} />
                </small>
              )}
            </span>
            <span>
              {line.amount_copper != null && line.amount_copper > 0 ? "+" : ""}
              <Money copper={line.amount_copper} />
            </span>
          </div>
          {line.amount_copper != null && (
            <div className={styles.barTrack}>
              <div
                className={styles.bar}
                style={{
                  width: `${Math.min(100, (Math.abs(line.amount_copper) / sale) * 100)}%`,
                }}
              />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
