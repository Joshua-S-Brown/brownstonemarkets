import { PageHead } from "../../ui/PageHead";
import { CharacterName } from "../../ui/CharacterName";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import type { components } from "../../api/schema";
import { get } from "../../api/client";
import { Money, moneyText } from "../../ui/Money";
import { ItemLink } from "../../ui/ItemLink";
import { Evidence } from "../../ui/Evidence";
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
  // Open on the top ranked craft, as the prototype does, rather than an empty page.
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
    <>
      <PageHead
        eyebrow="Recipe routes"
        title="Supply chains"
        subtitle="Where does the margin come from?"
      />
      <p>
        Cautious basis · Forcing is exploration only: Today still costs with the
        cheapest routes.
      </p>
      {query.error && <p role="alert">{query.error.message}</p>}
      <nav aria-label="Top ranked crafts">
        {query.data?.ranked.map((r) => (
          <button key={r.catalog_id + r.recipe_id} onClick={() => choose(r)}>
            {r.name} · {r.profession}
          </button>
        ))}
      </nav>
      <label>
        Find an output by name or item ID{" "}
        <input value={q} onChange={(e) => setQ(e.target.value)} />
      </label>
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
    </>
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
          <h2>{r.name}</h2>
          <p className={appStyles["summary-strip"]}>
            Batch {r.batch} · Spend <Money copper={r.spend_copper} />
            {r.can_add && (
              <>
                {" "}
                · Profit <Money copper={r.profit_copper} />
              </>
            )}
          </p>
          {r.reason && <p>{r.reason}</p>}
          {query.isFetching && <p role="status">Recalculating…</p>}
          <Graph route={r} force={force} />
          <h2>Per craft</h2>
          <Waterfall route={r} />
          <div className={styles.waterfall}>
            {r.waterfall.map((line, i) => (
              <p key={i}>
                <span>
                  {line.label}
                  {line.quantity != null && (
                    <>
                      {" "}
                      × {line.quantity} @{" "}
                      <Money copper={line.unit_cost_copper ?? null} />
                    </>
                  )}
                </span>
                <Money copper={line.amount_copper} />
              </p>
            ))}
          </div>
          <h2>Batch</h2>
          <label>
            Crafts: {batch}
            <input
              aria-label="Crafts"
              type="range"
              min={1}
              max={r.max_crafts}
              value={batch}
              onChange={(e) => setBatch(Number(e.target.value))}
            />
          </label>
          <p>
            Spend <Money copper={r.spend_copper} />
            {r.can_add && (
              <>
                {" "}
                · Profit <Money copper={r.profit_copper} />
              </>
            )}
          </p>
          {r.leaves.map((leaf) => (
            <p key={leaf.item_id}>
              <ItemLink id={leaf.item_id} name={leaf.name} /> × {leaf.quantity}{" "}
              · <Money copper={leaf.total_cost_copper} /> · {leaf.depth}
            </p>
          ))}
          <p>
            Listing depth is display only; these counts do not claim listings
            cover this batch. Held units never lower costs.
          </p>
          <button
            className={appStyles.primary}
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
          <details>
            <summary>Evidence · Cautious basis</summary>
            <Evidence data={{ ...r.evidence, source: r.source_evidence }} />
          </details>
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
  const positions = new Map<number, { x: number; y: number }>();
  const counts = new Map<number, number>();
  route.nodes.forEach((n) => {
    const index = counts.get(n.column) || 0;
    counts.set(n.column, index + 1);
    positions.set(n.item_id, { x: (max - n.column) * 310, y: index * 360 });
  });
  const height = Math.max(1, ...counts.values()) * 360;
  return (
    <div className={styles.panel} aria-label="Recipe graph">
      <div
        className={styles.graph}
        style={
          {
            "--graph-width": `${(max + 1) * 310}px`,
            "--graph-height": `${height}px`,
          } as React.CSSProperties
        }
      >
        <svg
          className={styles.edges}
          width={(max + 1) * 310}
          height={height}
          aria-label="Input quantities"
        >
          {route.edges.map((e) => {
            const parent = positions.get(e.parent)!,
              child = positions.get(e.child)!;
            return (
              <g key={e.parent + ":" + e.child}>
                <path
                  d={`M${child.x + 280},${child.y + 150} L${parent.x},${parent.y + 150}`}
                  fill="none"
                  stroke="currentColor"
                />
                <text
                  x={(child.x + 280 + parent.x) / 2}
                  y={(child.y + parent.y) / 2 + 140}
                >
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
          {route.nodes.map((n) => (
            <li
              key={n.item_id}
              className={styles.node}
              style={
                {
                  left: positions.get(n.item_id)!.x,
                  top: positions.get(n.item_id)!.y,
                  "--indent": `${n.column * 12}px`,
                } as React.CSSProperties
              }
            >
              <h3>
                <ItemLink id={n.item_id} name={n.name} quality={n.quality} />
              </h3>
              <p>
                {n.units} units per output craft ·{" "}
                {METHOD[n.method] ?? n.method}{" "}
                {n.forced && <strong>forced</strong>}
              </p>
              <p>
                <Money copper={n.unit_cost_copper} /> / unit
              </p>
              {n.options.length >= 2 && (
                <div role="group" aria-label={`${n.name} route`}>
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
              )}
              {n.forced && (
                <button onClick={() => force(n.item_id)}>
                  Reset to cheapest
                </button>
              )}
              {n.method === "craft" && <p>{n.maker}</p>}
              <details>
                <summary>Route evidence</summary>
                <Evidence data={{ route_note: n.route_note }} />
              </details>
              <p>
                {n.held == null
                  ? "Held: unknown"
                  : n.held === 0
                    ? n.at_least
                      ? "None seen in captured bags and banks"
                      : "None held"
                    : `Held: ${n.at_least ? "at least " : ""}${n.held}`}
              </p>
              {n.characters.length > 0 && (
                <details>
                  <summary>Team recipe status</summary>
                  {n.characters.map((c) => (
                    <p key={c.character.join(":")}>
                      <CharacterName character={c.character} /> ·{" "}
                      {c.craft_status} · {c.character_reason}
                    </p>
                  ))}
                </details>
              )}
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}

function Waterfall({ route }: { route: Route }) {
  const points = route.waterfall.flatMap((l) => [
    l.start_copper,
    l.end_copper ?? l.start_copper,
  ]);
  const low = Math.min(0, ...points),
    high = Math.max(1, ...points);
  const x = (n: number) => 10 + ((n - low) / (high - low)) * 580;
  return (
    <svg
      viewBox={`0 0 600 ${route.waterfall.length * 32}`}
      role="img"
      aria-label="Per craft copper waterfall"
      style={{ width: "100%", maxWidth: 620 }}
    >
      {route.waterfall.map((l, i) =>
        l.end_copper === null ? null : (
          <g key={i}>
            <title>
              {l.label}: {moneyText(l.amount_copper)}
            </title>
            <rect
              x={Math.min(x(l.start_copper), x(l.end_copper))}
              y={i * 32 + 4}
              width={Math.max(1, Math.abs(x(l.end_copper) - x(l.start_copper)))}
              height={24}
              fill={
                l.label === "Profit"
                  ? "var(--accent)"
                  : (l.amount_copper ?? 0) < 0
                    ? "var(--copper)"
                    : "var(--good)"
              }
            />
          </g>
        ),
      )}
    </svg>
  );
}
