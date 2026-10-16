import { Evidence } from "../../ui/Evidence";
import { Money } from "./Money";
import { ItemLink } from "../../ui/ItemLink";
import { DataGrid } from "../../ui/DataGrid";
import { Pill } from "../../ui/parts";
import type { Estimate, Group, Recipe } from "./types";
export function Cost({ estimate }: { estimate: Estimate }) {
  return estimate.complete ? (
    <Money copper={estimate.cost_copper ?? null} />
  ) : (
    <>incomplete: {estimate.reasons?.join("; ")}</>
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
          <Cost estimate={group.best.estimate} />
        </>
      ) : (
        "no valued recipe in reach"
      )}
    </p>
  );
}
function RecipeDetails({ recipe: r }: { recipe: Recipe }) {
  return (
    <details>
      <summary>{r.name} · How to get there</summary>
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
      <Steps estimate={r.estimate} />
      <Evidence data={r} />
    </details>
  );
}
export function Path({ groups, window }: { groups: Group[]; window: number }) {
  return (
    <>
      {groups.map((g) => (
        <section key={g.profession}>
          <h2>
            {g.profession} · {g.rank ?? "unknown"} / {g.max_rank ?? "unknown"}
          </h2>
          {g.best && (
            <section>
              <h3>Best next recipe</h3>
              <ItemLink id={g.best.output_item_id} name={g.best.name} />
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
                rows={g.recipes}
                columns={[
                  {
                    accessorKey: "name",
                    header: "Recipe",
                    cell: (c) => (
                      <ItemLink
                        id={c.row.original.output_item_id}
                        name={c.row.original.name}
                      />
                    ),
                  },
                  { accessorKey: "required_skill", header: "Skill" },
                  { accessorKey: "points_needed", header: "Points" },
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
                    cell: (c) => <Cost estimate={c.row.original.estimate} />,
                  },
                  {
                    accessorKey: "learn_from",
                    header: "Learn from",
                    cell: (c) => <Pill>{c.row.original.learn_from}</Pill>,
                  },
                  { accessorKey: "confidence", header: "Confidence" },
                ]}
              />
              {g.recipes.map((r) => (
                <RecipeDetails
                  key={`${String(r.catalog_id)}|${String(r.recipe_id)}`}
                  recipe={r}
                />
              ))}
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
