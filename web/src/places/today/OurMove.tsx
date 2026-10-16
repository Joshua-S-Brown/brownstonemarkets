import { useQueryClient, useMutation } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { useState, useSyncExternalStore } from "react";
import { Money } from "../../ui/Money";
import { Pill, Tip } from "../../ui/parts";
import { Evidence } from "../../ui/Evidence";
import { post } from "../../api/client";
import {
  type Craft,
  type Identity,
  type Plan,
  todayKey,
  choicesFor,
  keepLocal,
  writeState,
} from "./state";
const same = (a: Identity, b: Identity) =>
  a.catalog_id === b.catalog_id && a.recipe_id === b.recipe_id;
export function OurMove({ source, id }: { source: string; id: number }) {
  const client = useQueryClient();
  const [params] = useSearchParams();
  const view = params.get("view") === "level-up" ? "level-up" : "opportunities";
  const data = useSyncExternalStore(
    (cb) => client.getQueryCache().subscribe(cb),
    () => client.getQueryData<Plan>(todayKey(source)),
  );
  const mutation = useMutation({
    mutationFn: async (state: Plan["state"]) =>
      keepLocal(
        source,
        await post<Plan>("today/plan", source, { view, state }),
      ),
    onSuccess: (result) => {
      writeState(source, result.state);
      client.setQueryData(todayKey(source), result);
    },
  });
  if (!data) return null;
  // Session rows keep every craft shown this session, so an excluded craft can be included again.
  const shown = data.state.rows || [];
  const rows = [
    ...shown,
    ...data.plan.craft.filter((r) => !shown.some((s) => same(s, r))),
  ].filter((r) => r.output_item_id === id);
  if (!rows.length) return null;
  return (
    <section>
      <h2>Our move</h2>
      {rows.map((row) => (
        <Move
          key={row.catalog_id + row.recipe_id}
          data={data}
          remembered={row}
          pending={mutation.isPending}
          send={(state) => mutation.mutate(state)}
        />
      ))}
      <label>
        <input
          type="checkbox"
          checked={data.state.refill ?? true}
          disabled={mutation.isPending}
          onChange={(e) =>
            mutation.mutate({
              ...data.state,
              choices: choicesFor(data),
              refill: e.target.checked,
            })
          }
        />
        Refill freed gold
      </label>
      {mutation.error && <p role="alert">{mutation.error.message}</p>}
    </section>
  );
}
function Move({
  data,
  remembered,
  pending,
  send,
}: {
  data: Plan;
  remembered: Craft;
  pending: boolean;
  send: (state: Plan["state"]) => void;
}) {
  const [invalid, setInvalid] = useState("");
  const row = data.plan.craft.find((r) => same(r, remembered));
  const maximum =
    data.plan.choice_limits?.find((l) => same(l, remembered))?.maximum ??
    remembered.feasible_size;
  const update = (size: number | null) =>
    send({
      ...data.state,
      choices: choicesFor(data).map((c) =>
        same(c, remembered) ? { ...c, batch_size: size } : c,
      ),
    });
  return (
    <div>
      {row ? (
        <>
          <p>
            Reserved profit <Money copper={row.headline_profit_copper} />
            {row.profit_basis}
          </p>
          <Tip text={row.confidence_reasons.join("; ")}>
            <Pill>{row.confidence} confidence</Pill>
          </Tip>
          {row.warnings_text && <p>{row.warnings_text}</p>}
          <p>
            {row.made_by || "Maker unknown"} · {row.batch_size} crafts
          </p>
        </>
      ) : (
        <p>Not in tonight’s plan.</p>
      )}
      <label>
        <input
          type="checkbox"
          checked={!!row}
          disabled={pending || maximum === 0}
          onChange={(e) =>
            update(e.target.checked ? remembered.batch_size || 1 : null)
          }
        />
        Include craft
      </label>
      <label>
        Batch size{" "}
        <input
          aria-label="Batch size"
          type="number"
          min={1}
          max={Math.max(1, maximum)}
          defaultValue={row?.batch_size || 1}
          key={row?.batch_size}
          disabled={pending || maximum === 0}
          onBlur={(e) => {
            const n = Number(e.target.value);
            if (n === row?.batch_size) return;
            if (!Number.isInteger(n) || n < 1 || n > maximum)
              return setInvalid(
                `Batch must be a whole number from 1 to ${maximum}.`,
              );
            setInvalid("");
            update(n);
          }}
        />
      </label>
      {invalid && <p role="alert">{invalid}</p>}
      <details>
        <summary>Reserved craft evidence</summary>
        <Evidence
          data={{
            craft: row || remembered,
            sale: row ? data.plan.sell[data.plan.craft.indexOf(row)] : {},
          }}
        />
      </details>
    </div>
  );
}
