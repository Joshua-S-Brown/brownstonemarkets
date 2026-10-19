import styles from "./records.module.css";
import { Panel } from "../ui/Panel";
import { CharacterWords } from "../ui/CharacterWords";
import { UtcTime } from "../ui/UtcTime";
import { CharacterName } from "../ui/CharacterName";
import { useQuery } from "@tanstack/react-query";
import { get } from "../api/client";
import type { Activity, Chain, Recipe } from "../api/market";
import { ItemLink } from "../ui/ItemLink";
import { Money } from "../ui/Money";
import { ErrorState } from "../ui/parts";
import { Evidence } from "../ui/Evidence";
// The Board's CRAFT-05 label in words; meaning unchanged.
export const actionWords = (label: string | null | undefined) =>
  label === "potential craft" ? "Could craft for profit" : label;
function RecipeRow({
  r,
  used,
  source,
}: {
  r: Recipe;
  used: boolean;
  source: string;
}) {
  return (
    <section>
      <h3>
        <ItemLink id={r.item_id} name={r.name} /> × {r.output_quantity} ·{" "}
        {r.profession.charAt(0).toUpperCase() + r.profession.slice(1)}
      </h3>
      {
        <a
          href={
            "/app/chains?" +
            new URLSearchParams({
              source,
              catalog: r.catalog_id || "",
              recipe: String(r.recipe_id || ""),
            })
          }
        >
          Open in Supply chains
        </a>
      }
      {used && (
        <p>
          {r.quantity} {r.quantity === 1 ? "unit" : "units"} per craft
        </p>
      )}
      <p>{actionWords(r.reason)}</p>
      <p>
        Board profit per craft: <Money copper={r.profit_copper} />
      </p>
      {r.vendor_capped && (
        <p>
          capped at vendor price <Money copper={r.vendor_price_cap_copper} />
        </p>
      )}
      {r.warnings.map((w) => (
        <p key={w}>{w}</p>
      ))}
      {!used &&
        r.materials.map((m, i) => (
          <p key={i} style={{ paddingLeft: m.depth * 16 }}>
            <ItemLink id={m.item_id} name={m.item_name} /> × {m.quantity} ·{" "}
            {m.method} · <Money copper={m.unit_cost_copper} /> / unit ·{" "}
            <Money copper={m.total_cost_copper} /> total{" "}
            <CharacterWords
              text={m.maker ?? ""}
              characters={r.characters.map((c) => c.character)}
            />{" "}
          </p>
        ))}
      {!used && (
        <details>
          <summary>Expanded quantities</summary>
          {r.expanded.map((m, i) => (
            <p key={i}>
              <ItemLink id={m.item_id} name={m.name} /> × {m.quantity}
            </p>
          ))}
        </details>
      )}
      <details>
        <summary>Route evidence</summary>
        <Evidence
          data={{
            recipe_id: r.recipe_id,
            catalog_id: r.catalog_id,
            route_reason: actionWords(r.reason),
            route_notes: r.materials.map((m) => m.route_note),
          }}
        />
      </details>
      <details>
        <summary>Team eligibility</summary>
        {r.characters.length === 0
          ? "Team: Unknown"
          : r.characters.map((c, i) => (
              <p key={i}>
                <CharacterName character={c.character} />:{" "}
                {actionWords(c.craft_status)} · {c.character_reason}
              </p>
            ))}
      </details>
    </section>
  );
}
export function ItemChain({ source, id }: { source: string; id: number }) {
  const query = useQuery({
    queryKey: [source, "chain", id],
    queryFn: ({ signal }) => get<Chain>(`items/${id}/chain`, source, signal),
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
  if (!query.data) return <p>Loading catalog routes…</p>;
  const c = query.data;
  return (
    <>
      {!c.in_chain && (
        <p>This item is in no compatible catalog. Price evidence only.</p>
      )}
      {!!c.best_uses?.length && (
        <section>
          <h2>Best use of one unit</h2>
          <p>
            Newest scan estimates after the auction cut. Listings are not sales;
            speed and demand unknown.
          </p>
          <table className={styles.uses}>
            <thead>
              <tr>
                <th>Option</th>
                <th>Per unit</th>
                <th>Who can craft</th>
              </tr>
            </thead>
            <tbody>
              {c.best_uses.map((o, i) => (
                <tr key={i}>
                  <td>
                    {o.action}
                    {o.reason && <p>{o.reason}</p>}
                    {o.intermediate && (
                      <p>
                        intermediate: valued at its own sale, not a Board row
                      </p>
                    )}
                    {o.vendor_capped && (
                      <p>
                        capped at vendor price{" "}
                        <Money copper={o.vendor_price_cap_copper ?? null} />
                      </p>
                    )}
                  </td>
                  <td>
                    <Money copper={o.value_copper} />
                    {o.over_selling_copper != null &&
                      o.over_selling_copper > 0 && (
                        <p>
                          +<Money copper={o.over_selling_copper} /> a unit over
                          selling
                        </p>
                      )}
                  </td>
                  <td>
                    {o.eligibility}
                    {o.characters
                      .filter((c) =>
                        ["Known", "Train now"].includes(c.craft_status),
                      )
                      .map((c, j) => (
                        <p key={j}>
                          <CharacterName character={c.character} />:{" "}
                          {c.craft_status}
                        </p>
                      ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
      {(["made_from", "used_in"] as const).map((key) => (
        <section key={key}>
          <h2>{key === "made_from" ? "Made from" : "Used in"}</h2>
          {c[key].length === 0 && (
            <p>
              No compatible recipe {key === "made_from" ? "makes" : "consumes"}{" "}
              this item.
            </p>
          )}
          {c[key].map((r, i) => (
            <RecipeRow key={i} r={r} used={key === "used_in"} source={source} />
          ))}
        </section>
      ))}
      <h2>Skill-up bands</h2>
      {c.demand.map((d, i) => (
        <p key={i}>
          {d.professions.join(" · ")}: {d.bands.join(", ")}
        </p>
      ))}
      <p>
        Catalog quantities and bands, not observed demand or sales. Variants
        never feed base-item routes.
      </p>
    </>
  );
}
export function ItemActivity({ source, id }: { source: string; id: number }) {
  const query = useQuery({
    queryKey: [source, "activity", id],
    queryFn: ({ signal }) =>
      get<Activity>(`items/${id}/activity`, source, signal),
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
  if (!query.data) return <p>Loading our activity…</p>;
  const a = query.data;
  return (
    <>
      <h2>Your sales</h2>
      {a.sales_error && <p>Sales evidence unavailable: {a.sales_error}</p>}
      {!a.your_sales.length && <p>none resolved yet</p>}
      {!!a.your_sales.length && (
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th>Character</th>
                <th>Sold of posted</th>
                <th>Each after cut</th>
                <th>Newest</th>
              </tr>
            </thead>
            <tbody>
              {a.your_sales.map((s, i) => (
                <tr key={i}>
                  <td>
                    <CharacterName
                      character={[
                        s.character[0],
                        s.character[1],
                        s.character[2],
                      ]}
                    />
                  </td>
                  <td>
                    {s.sold} of {s.posted} sold
                    <details>
                      <summary>Outcomes</summary>
                      {s.expired} expired · {s.cancelled} cancelled ·{" "}
                      {s.sold + s.expired + s.cancelled} resolved
                    </details>
                  </td>
                  <td>
                    <Money copper={s.average_copper} />
                  </td>
                  <td>
                    {s.newest_sale ? (
                      <UtcTime
                        value={new Date(s.newest_sale * 1000).toISOString()}
                      />
                    ) : (
                      "none yet"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p>
        Unidentified seller invoices in this source and market:{" "}
        {a.unidentified_sales}
      </p>
      <h2>Holdings</h2>
      <p>
        {a.at_least ? "at least " : ""}
        {a.held ?? "unknown"} held
        {a.holdings_warning ? ` · ${a.holdings_warning}` : ""}
      </p>
      {a.holdings.map((h, i) => (
        <p key={i}>
          {h.character} · {h.realm} · {h.kind}: {h.units}
        </p>
      ))}
      <details>
        <summary>Capture evidence</summary>
        <Evidence data={{ captures: a.captures }} />
      </details>
    </>
  );
}

export function ItemGathering({ source, id }: { source: string; id: number }) {
  const query = useQuery({
    queryKey: [source, "activity", id],
    queryFn: ({ signal }) =>
      get<Activity>(`items/${id}/activity`, source, signal),
  });
  if (query.error)
    return (
      <p>
        Farming evidence unavailable. Use Data to check saved character
        evidence.
      </p>
    );
  if (!query.data) return <p>Loading our gathering evidence…</p>;
  const a = query.data;
  return (
    <>
      <h2>Where to get it</h2>
      {a.farming.length === 0 && <p>not gathered yet</p>}
      {a.farming.map((c, i) => (
        <section key={i}>
          <h3>
            <CharacterName
              character={[c.character[0], c.character[1], c.character[2]]}
            />
          </h3>
          {c.farming.rows.map((r, j) => (
            <p key={j}>
              {r.zone || "unknown zone"} · {r.source_kind} ·{" "}
              {r.units_per_hour.toFixed(0)} units/hour ·{" "}
              {r.value_per_hour_copper === null ? (
                "no price"
              ) : (
                <>
                  <Money copper={r.value_per_hour_copper} /> / hour
                </>
              )}{" "}
              · typical unit <Money copper={r.typical_price_copper ?? null} /> ·{" "}
              {((r.seconds ?? 0) / 60).toFixed(1)} evidence minutes ·{" "}
              {r.stretches ?? 0} stretches
            </p>
          ))}
          <h3>Farming spots</h3>
          {c.farming.spots.map((s, j) => (
            <Panel key={j} title={s.zone || `Map ${s.map_id}`}>
              <p>
                {s.zone || `Map ${s.map_id}`} ·{" "}
                {s.npc_id ? (
                  <a
                    href={`https://www.wowhead.com/classic/npc=${s.npc_id}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {s.mob_name ?? "Unknown creature"}
                  </a>
                ) : (
                  s.mob
                )}{" "}
                · <Money copper={s.value_per_hour_copper ?? null} /> / hour
              </p>
              <p>
                {((s.seconds ?? 0) / 60).toFixed(1)} minutes · {s.stretches}{" "}
                stretches · {s.position} · also looted:{" "}
                {s.also_looted_names
                  ?.map((name) => name ?? "Unknown creature")
                  .join(", ") || "—"}
              </p>
              <p>
                {s.coin_copper === null
                  ? "Coin unavailable"
                  : "Captured coin: "}{" "}
                {s.coin_copper !== null && (
                  <Money copper={s.coin_copper ?? null} />
                )}{" "}
                · no price: {s.no_price_items ?? 0} items /{" "}
                {s.no_price_units ?? 0} units
              </p>
            </Panel>
          ))}
          <p>{c.farming.excluded_stretches ?? 0} skipped stretches</p>
          <details>
            <summary>Farming rates and containing spots</summary>
            <Evidence data={c.farming} />
          </details>
        </section>
      ))}
      <p>
        Your own past sessions, not a promise; launch respawn competition
        differs; listings are not sales.
      </p>
      <a href={a.wowhead_url} target="_blank" rel="noreferrer">
        Wowhead drop sources and places
      </a>
    </>
  );
}
