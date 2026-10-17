// Display-only types for the existing evidence dictionaries in the OpenAPI contracts.
import type { components } from "./schema";
export type Signal = {
  item_id: number;
  item_name: string;
  variant_id: string | null;
  variant_state: string | null;
  crowding: string;
  listings: number;
  units: number;
  largest_stack_units: number;
  churn: { changed: number; pairs: number };
  overshoot: {
    label: string;
    typical_copper: number | null;
    days: number;
    scans: number;
    ratio: { numerator: number; denominator: number } | null;
  };
};
export type Row = Omit<components["schemas"]["MarketRow"], "signal"> & {
  signal: Signal | null;
};
export type Market = Omit<components["schemas"]["Market"], "rows" | "pulse"> & {
  rows: Row[];
  pulse: { cheap: Signal[]; high: Signal[]; early: Removal[] };
};
export type Removal = {
  item_id: number;
  item_name: string;
  variant_id: string | null;
  variant_state: string | null;
  early: { units: number; listings: number };
  expiry: { units: number; listings: number };
  unknown: { units: number; listings: number };
  without_buyout: { earlier: number; later: number };
  evidence: unknown[];
};
export type History = Omit<
  components["schemas"]["History"],
  "points" | "scans"
> & {
  removals: {
    note: string;
    pairs: {
      skipped: boolean;
      earlier: { finished_at: string };
      later: { finished_at: string };
      gap: number;
      items: Removal[];
    }[];
  };
  removals_error: string | null;
  scans: { scan_id: string; finished_at: string }[];
  points: {
    scan_id: string;
    finished_at: string;
    metrics: {
      min_buyout: number | null;
      market_value: number | null;
      units: number;
    } | null;
  }[];
};
export type Ladder = components["schemas"]["Ladder"];
export type Recipe = {
  catalog_id?: string;
  recipe_id?: number;
  item_id: number;
  name: string;
  output_quantity: number;
  profession: string;
  quantity: number;
  profit_copper: number | null;
  reason: string;
  materials: {
    item_id: number;
    item_name: string;
    quantity: number;
    depth: number;
    method: string;
    unit_cost_copper: number | null;
    total_cost_copper: number | null;
    route_note?: string;
    maker?: string;
  }[];
  characters: {
    character: string;
    craft_status: string;
    character_reason: string;
  }[];
  expanded: { item_id: number; name: string; quantity: number }[];
  warnings: string[];
  vendor_capped: boolean;
  vendor_price_cap_copper: number | null;
};
export type Chain = {
  in_chain: boolean;
  demand: { professions: string[]; bands: string[] }[];
  made_from: Recipe[];
  used_in: Recipe[];
};
export type Activity = Omit<
  components["schemas"]["Activity"],
  "your_sales" | "holdings" | "farming"
> & {
  your_sales: {
    character: string[];
    posted: number;
    sold: number;
    expired: number;
    cancelled: number;
    newest_sale: number | null;
    average_copper: number | null;
  }[];
  holdings: { character: string; realm: string; kind: string; units: number }[];
  farming: {
    character: string[];
    farming: {
      rows: {
        item_id: number;
        units: number;
        units_per_hour: number;
        zone?: string;
        source_kind?: string;
        typical_price_copper?: number | null;
        seconds?: number;
        stretches?: number;
        value_per_hour_copper: number | null;
      }[];
      excluded_stretches?: number;
      spots: {
        zone?: string;
        map_id?: number;
        npc_id?: number | null;
        mob?: string;
        value_per_hour_copper?: number | null;
        seconds?: number;
        stretches?: number;
        position?: string;
        also_looted_labels?: string[];
        coin_copper?: number | null;
        no_price_items?: number;
        no_price_units?: number;
      }[];
    };
  }[];
};
