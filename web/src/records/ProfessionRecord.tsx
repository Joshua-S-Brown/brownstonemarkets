import { Fragment, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import * as Tabs from "@radix-ui/react-tabs";
import { get } from "../api/client";
import type { components } from "../api/schema";
import { CharacterName } from "../ui/CharacterName";
import { ItemLink } from "../ui/ItemLink";
import { Evidence } from "../ui/Evidence";
import { Tile } from "../ui/Tile";
import { ErrorState } from "../ui/parts";
import { Money } from "../places/team/Money";
import { title } from "../places/team/Hiring";
import kit from "../ui/components.module.css";
import record from "./records.module.css";

type Data = components["schemas"]["ProfessionRecord"];

export function ProfessionRecord({
  source,
  profession,
}: {
  source: string;
  profession: string;
}) {
  const query = useQuery({
    queryKey: [source, "team-profession", profession],
    queryFn: ({ signal }) =>
      get<components["schemas"]["ProfessionRecord"]>(
        "team/profession/" + encodeURIComponent(profession),
        source,
        signal,
      ),
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
  const data = query.data;
  if (!data) return <p role="status">Loading profession…</p>;
  return (
    <>
      <header className={record.header}>
        <h1>{title(profession)}</h1>
      </header>
      <div className={record.facts} aria-label="Profession facts">
        <Tile label="Holders" value={data.holders.length} />
        <Tile label="Catalog recipes" value={data.rows.length} />
        <Tile label="Catalogs" value={data.catalogs.length} />
      </div>
      {data.holders.map((h) => (
        <p key={h.character.join("|")}>
          <CharacterName character={h.character} /> · {h.rank ?? "unknown"}/
          {h.max_rank ?? "unknown"} · {h.known_count ?? "unknown"} known catalog
          recipes
          {h.note && <> · {h.note}</>}
        </p>
      ))}
      {!data.holders.length && <p>No evidenced holder.</p>}
      <Tabs.Root defaultValue="Recipes">
        <Tabs.List aria-label="Profession record">
          <Tabs.Trigger value="Recipes">Recipes</Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="Recipes">
          <RecipeTable
            profession={title(profession)}
            holders={data.holders}
            rows={data.rows}
          />
        </Tabs.Content>
      </Tabs.Root>
      <footer>
        <h2>Profession evidence</h2>
        {data.catalogs.map((c) => (
          <p key={c.catalog_id}>
            {c.catalog_id} · version {c.catalog_version} · {c.coverage}
          </p>
        ))}
        <Evidence data={data.evidence} />
      </footer>
    </>
  );
}

function RecipeTable({
  profession,
  holders,
  rows,
}: {
  profession: string;
  holders: Data["holders"];
  rows: Data["rows"];
}) {
  const [open, setOpen] = useState<Set<string>>(new Set());
  const bands = [...new Set(rows.map((r) => r.band))];
  const width = 3 + holders.length;
  function toggle(key: string) {
    const next = new Set(open);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setOpen(next);
  }
  return (
    <div className={`${kit["table-wrap"]} ${record.recipes}`}>
      <table className={kit.compact} aria-label={`${profession} recipes`}>
        <thead>
          <tr>
            <th scope="col">Recipe</th>
            <th scope="col" className={kit.num}>
              Skill
            </th>
            {holders.map((h) => (
              <th key={h.character.join("|")} scope="col">
                <CharacterName character={h.character} />
              </th>
            ))}
            <th scope="col">Profit per craft</th>
          </tr>
        </thead>
        <tbody>
          {bands.map((band) => (
            <Fragment key={band}>
              <tr>
                <th colSpan={width} scope="colgroup">
                  {band === "skill unknown" ? band : `Skill ${band}`}
                </th>
              </tr>
              {rows
                .filter((r) => r.band === band)
                .map((r) => {
                  const key = r.catalog_id + ":" + r.recipe_id;
                  const expanded = open.has(key);
                  return (
                    <Fragment key={key}>
                      <tr>
                        <td>
                          <div className={record.recipe}>
                            <button
                              aria-expanded={expanded}
                              aria-label={`${r.name} details`}
                              onClick={() => toggle(key)}
                            >
                              {expanded ? "▾" : "▸"}
                            </button>
                            <ItemLink id={r.output_item_id} name={r.name} />
                          </div>
                        </td>
                        <td className={kit.num}>
                          {r.required_skill ?? "unknown"}
                        </td>
                        {r.statuses.map((s, i) => (
                          <td key={holders[i].character.join("|")}>
                            {s.craft_status}
                            {s.craft_status === "Train now" && (
                              <span className={record.sub}>
                                training{" "}
                                <Money copper={s.training_cost_copper} />
                              </span>
                            )}
                          </td>
                        ))}
                        <td className={record.profit}>
                          {r.profit_copper != null && (
                            <>
                              <Money copper={r.profit_copper} />
                              {r.board_reason && " · "}
                            </>
                          )}
                          {r.board_reason}
                        </td>
                      </tr>
                      {expanded && (
                        <tr className={record.detail}>
                          <td colSpan={width}>
                            <p>
                              {r.range_text || "skill-up colours recorded"} ·
                              learned from {r.learn_from}
                            </p>
                            <p>
                              Materials:{" "}
                              {r.materials.length
                                ? r.materials.map((m, i) => (
                                    <span key={m.item_id}>
                                      {i > 0 && " · "}
                                      {m.quantity} ×{" "}
                                      <ItemLink id={m.item_id} name={m.name} />
                                    </span>
                                  ))
                                : "none listed"}
                            </p>
                            {r.statuses.map(
                              (s, i) =>
                                s.character_reason && (
                                  <p key={holders[i].character.join("|")}>
                                    <CharacterName
                                      character={holders[i].character}
                                    />{" "}
                                    · {s.craft_status} · {s.character_reason}
                                  </p>
                                ),
                            )}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
