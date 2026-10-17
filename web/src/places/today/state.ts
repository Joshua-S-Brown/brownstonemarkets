import type { QueryClient } from "@tanstack/react-query";
import { post } from "../../api/client";
import type { components } from "../../api/schema";
export type Choice = {
  catalog_id: string;
  recipe_id: number;
  batch_size: number | null;
};
export type Identity = Omit<Choice, "batch_size">;
export type Craft = Choice & {
  output_item_id: number;
  output_name: string;
  made_by: string | null;
  profession: string;
  headline_profit_copper: number;
  headline_per_craft_copper: number;
  profit_basis: string;
  warnings_text?: string;
  confidence: string;
  confidence_reasons: string[];
  feasible_size: number;
};
export type State = {
  hide_low?: boolean;
  context?: string;
  queue_identity?: string;
  ticks?: Record<string, boolean>;
  choices?: Choice[] | null;
  feasible_choices?: Choice[];
  refill?: boolean;
  rows?: Craft[];
};
export type Plan = Omit<
  components["schemas"]["TodayPlan"],
  "state" | "plan"
> & {
  state: State;
  plan: {
    craft: Craft[];
    unplanned?: import("./Opportunities").Unplanned[];
    sell: ({ output_item_id: number } & Record<string, unknown>)[];
    queue: {
      lines: object[];
      mail_note: string;
      expected_profit_copper: number | null;
      gold_needed_copper: number;
    };
    freshness: {
      stale: boolean;
      age_hours: number | null;
      upstream_known: boolean;
    };
    dropped_choices: (Identity & { reason: string })[];
    choice_limits?: (Identity & { maximum: number })[];
    holdings_warning?: string;
    catalog_warnings?: string[];
  };
};
export const todayKey = (source: string) => [source, "today"];
const storageKey = (source: string) => "brownstone-today-" + source;
export function readState(source: string): State {
  try {
    const stored: unknown = JSON.parse(
      sessionStorage.getItem(storageKey(source)) || "{}",
    );
    return stored && typeof stored === "object" && !Array.isArray(stored)
      ? (stored as State)
      : {};
  } catch {
    return {};
  }
}
export function writeState(source: string, state: State) {
  sessionStorage.setItem(storageKey(source), JSON.stringify(state));
}
export function choicesFor(data: Plan): Choice[] {
  return (
    data.state.choices ||
    (data.state.rows || []).map((r) => ({
      catalog_id: r.catalog_id,
      recipe_id: r.recipe_id,
      batch_size: r.batch_size,
    }))
  );
}
// Ticks or Hide Low changed while a request was in flight are kept unless the response's
// Queue identity (or context) changed, which resets them on the server.
export function keepLocal(source: string, plan: Plan): Plan {
  const local = readState(source);
  if (
    local.context !== plan.state.context ||
    local.queue_identity !== plan.state.queue_identity
  )
    return plan;
  return {
    ...plan,
    state: {
      ...plan.state,
      ticks: local.ticks ?? plan.state.ticks,
      hide_low: local.hide_low ?? plan.state.hide_low,
    },
  };
}

export async function addToTonight(
  source: string,
  choice: Choice,
  client: QueryClient,
) {
  const current = await post<Plan>("today/plan", source, {
    state: readState(source),
  });
  const choices = choicesFor(current).filter(
    (c) =>
      c.catalog_id !== choice.catalog_id || c.recipe_id !== choice.recipe_id,
  );
  choices.push(choice);
  const result = await post<Plan>("today/plan", source, {
    state: { ...current.state, choices },
  });
  writeState(source, result.state);
  await client.invalidateQueries({ queryKey: todayKey(source) });
  return {
    batch_size: choice.batch_size,
    reason: result.plan.dropped_choices.find(
      (c) =>
        c.catalog_id === choice.catalog_id && c.recipe_id === choice.recipe_id,
    )?.reason,
  };
}
