import { useState } from "react";
import { useInspector } from "../../app/InspectorContext";
import { PlanText } from "../today/PlanText";
import { Evidence } from "../../ui/Evidence";
import { Money } from "./Money";
import { ItemLink } from "../../ui/ItemLink";
import { DataGrid } from "../../ui/DataGrid";
import { Tip } from "../../ui/parts";
import record from "../../records/records.module.css";
import type { Estimate, Group, Recipe } from "./types";
export function Cost({
  estimate,
  tip = false,
}: {
  estimate: Estimate;
  tip?: boolean;
}) {
  return (
    <>
      {estimate.complete ? (
        <Money copper={estimate.cost_copper ?? null} />
      ) : (
        <>
          incomplete: <PlanText text={estimate.reasons?.join("; ") ?? ""} />
        </>
      )}
      {tip && !!estimate.material_notes?.length && (
        <Tip text={estimate.material_notes.join("\n")}>Materials ⓘ</Tip>
      )}
    </>
  );
}
export function Materials({
  estimate,
}: {
  estimate: Pick<Estimate, "material_notes">;
}) {
  return (
    <>
      {estimate.material_notes?.map((text, i) => (
        <p key={i}>
          <PlanText text={text} />
        </p>
      ))}
    </>
  );
}
export function Steps({ estimate }: { estimate: Estimate }) {
  return (
    <details>
      <summary>Cost steps</summary>
      {estimate.steps?.length ? (
        <DataGrid
          rows={estimate.steps}
          columns={[
            { accessorKey: "rank", header: "Rank" },
            { accessorKey: "recipe", header: "Recipe" },
            { accessorKey: "expected_crafts", header: "Expected crafts" },
            {
              accessorKey: "cost_copper",
              header: "Cost",
              cell: (c) => <Money copper={c.getValue() as number | null} />,
            },
            {
              accessorKey: "training_cost_copper",
              header: "Training",
              cell: (c) => <Money copper={c.getValue() as number | null} />,
            },
          ]}
        />
      ) : (
        <p>No cost steps available.</p>
      )}
    </details>
  );
}
export function NextStep({ group }: { group: Group }) {
  return (
    <p>
      Next step · {group.profession}:{" "}
      {group.next_step === "note" ? (
        group.note
      ) : group.best ? (
        <>
          <ItemLink id={group.best.output_item_id} name={group.best.name} /> · +
          {group.best.points_needed} points ·{" "}
          <Money copper={group.best.profit_copper} />
        </>
      ) : (
        "no valued recipe in reach"
      )}
    </p>
  );
}
function RecipeDetails({ recipe: r }: { recipe: Recipe }) {
  const [open, setOpen] = useState(false);
  return (
    <details
      onToggle={(e) => {
        e.stopPropagation();
        setOpen(e.currentTarget.open);
      }}
    >
      <summary>{r.name} · How to get there</summary>
      {open && (
        <>
          <p>
            {String(r.craft_status ?? "unknown")} ·{" "}
            {String(r.character_reason ?? "")}
          </p>
          <p>
            Learning: {r.learn_from} · Training:{" "}
            {r.training_cost_copper == null ? (
              "cost unknown"
            ) : (
              <Money copper={r.training_cost_copper} />
            )}
            {r.payback.status === "crafts"
              ? ` · pays back training in ${r.payback.crafts} crafts`
              : r.payback.status !== "absent"
                ? ` · pays back training: ${r.payback.status}`
                : ""}
          </p>
          <p>
            Estimated cost: <Cost estimate={r.estimate} />
          </p>
          <Materials estimate={r.estimate} />
          <Steps estimate={r.estimate} />
          <Evidence data={r} />
        </>
      )}
    </details>
  );
}
export function Path({
  groups,
  window,
  catalogProfessions = {},
}: {
  groups: Group[];
  window: number;
  catalogProfessions?: Record<string, string>;
}) {
  const inspect = useInspector();
  return (
    <>
      {groups.map((g) => (
        <section key={g.profession}>
          <h2>
            {catalogProfessions[Number(g.skill_id)] ? (
              <button
                onClick={() =>
                  inspect({
                    profession: catalogProfessions[Number(g.skill_id)],
                  })
                }
              >
                {g.profession}
              </button>
            ) : (
              g.profession
            )}{" "}
            · {g.rank ?? "unknown"} / {g.max_rank ?? "unknown"}
          </h2>
          {g.best && (
            <section className={record.best}>
              <h3>Best next recipe</h3>
              <ItemLink id={g.best.output_item_id} name={g.best.name} />{" "}
              <Tip
                text={`${g.best.points_needed} points · ${g.best.confidence ?? "unknown"} confidence · ${g.best.learn_from}`}
              >
                ⓘ
              </Tip>
              <p>
                needs skill {g.best.required_skill ?? "unknown"} ·{" "}
                {g.best.learn_from}
              </p>
              <p>
                Then earns <Money copper={g.best.profit_copper} /> per craft
              </p>
              <p>
                Cost to get there: <Cost estimate={g.best.estimate} />
              </p>
              <Materials estimate={g.best.estimate} />
            </section>
          )}
          {g.alternative && (
            <section>
              <h3>
                {g.alternative_kind === "learn"
                  ? "Or learn now"
                  : "Pattern worth hunting"}
              </h3>
              <ItemLink
                id={g.alternative.output_item_id}
                name={g.alternative.name}
              />
              <p>
                {g.alternative.learn_from} ·{" "}
                <Money copper={g.alternative.profit_copper} /> per craft · needs
                skill {g.alternative.required_skill}
              </p>
              <p>
                {g.alternative_kind === "learn"
                  ? "reliable while you look for the pattern"
                  : "look for the pattern on the auction house or farm it; drops are not guaranteed"}
              </p>
            </section>
          )}
          {!!g.note && <p>{g.note}</p>}
          {g.recipes.length ? (
            <>
              <h3>Reachable recipes</h3>
              <DataGrid
                rows={g.recipes
                  .filter((r) => r.profit_copper != null)
                  .filter(
                    (r) =>
                      r.recipe_id !== g.best?.recipe_id ||
                      r.catalog_id !== g.best?.catalog_id,
                  )}
                density="compact"
                columns={[
                  {
                    accessorKey: "name",
                    header: "Recipe",
                    cell: (c) => (
                      <>
                        <ItemLink
                          id={c.row.original.output_item_id}
                          name={c.row.original.name}
                        />
                        <Tip
                          text={`${c.row.original.points_needed} points · ${c.row.original.confidence} confidence · ${c.row.original.learn_from}`}
                        >
                          ⓘ
                        </Tip>
                      </>
                    ),
                  },
                  { accessorKey: "required_skill", header: "Skill" },
                  {
                    accessorKey: "profit_copper",
                    header: "Earns per craft",
                    cell: (c) => (
                      <Money copper={c.row.original.profit_copper} />
                    ),
                  },
                  {
                    id: "cost",
                    header: "Cost to reach",
                    accessorFn: (r) => r.estimate.cost_copper,
                    cell: (c) => <Cost estimate={c.row.original.estimate} tip />,
                  },
                ]}
              />
              {g.recipes
                .filter((r) => r.profit_copper != null)
                .map((r) => (
                  <RecipeDetails
                    key={`${String(r.catalog_id)}|${String(r.recipe_id)}`}
                    recipe={r}
                  />
                ))}
              {g.recipes.some((r) => r.profit_copper == null) && (
                <details>
                  <summary>
                    {g.recipes.filter((r) => r.profit_copper == null).length}{" "}
                    more without a price
                  </summary>
                  {g.recipes
                    .filter((r) => r.profit_copper == null)
                    .map((r, i) => (
                      <RecipeDetails key={i} recipe={r} />
                    ))}
                </details>
              )}
            </>
          ) : (
            <p>
              {g.gathering
                ? `${g.profession} levels by gathering, not crafting`
                : `No catalog recipe within the next ${window} points`}
            </p>
          )}
        </section>
      ))}
    </>
  );
}
