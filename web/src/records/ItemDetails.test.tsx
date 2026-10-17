import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { ItemRecord } from "./ItemRecord";
import { ItemActivity, ItemChain, ItemGathering } from "./ItemDetails";
import type { Recipe } from "../api/market";
afterEach(() => vi.unstubAllGlobals());
function host(ui: React.ReactNode) {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}
const recipe: Recipe = {
  catalog_id: "tailoring",
  recipe_id: 2963,
  item_id: 2996,
  name: "Bolt",
  quantity: 2,
  output_quantity: 1,
  profession: "Tailoring",
  profit_copper: null,
  reason: "Intermediate: no Action Board profit row",
  characters: [],
  warnings: [],
  expanded: [{ item_id: 2589, name: "Linen", quantity: 2 }],
  materials: [
    {
      item_id: 2589,
      item_name: "Linen",
      quantity: 2,
      depth: 0,
      method: "buy",
      unit_cost_copper: 11,
      total_cost_copper: 22,
    },
  ],
  vendor_capped: false,
  vendor_price_cap_copper: null,
};
it("renders linked routes, quantities, unknown intermediate profit and team eligibility", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        in_chain: true,
        made_from: [recipe],
        used_in: [{ ...recipe, profit_copper: 123 }],
        demand: [{ professions: ["Tailoring"], bands: ["1–45"] }],
      }),
    })),
  );
  host(<ItemChain source="one" id={2996} />);
  await screen.findAllByText("Intermediate: no Action Board profit row", {
    exact: false,
  });
  expect(screen.getAllByText("Linen")).toHaveLength(2);
  expect(screen.getByText("2 units per craft")).toBeTruthy();
  expect(screen.getAllByText("Team: Unknown")).toHaveLength(2);
  expect(screen.getByText("22c")).toBeTruthy();
  expect(screen.getByText("Tailoring: 1–45")).toBeTruthy();
  expect(
    screen
      .getByRole("link", { name: "Open in Supply chains" })
      .getAttribute("href"),
  ).toBe("/app/chains?source=one&catalog=tailoring&recipe=2963");
});
it("renders sales outcomes, lower-bound holdings and gathering for every scoped character", async () => {
  const data = {
    your_sales: [
      {
        character: ["Maker", "Realm", "Alliance"],
        posted: 5,
        sold: 4,
        expired: 1,
        cancelled: 0,
        newest_sale: 2000,
        average_copper: 42,
      },
    ],
    unidentified_sales: 1,
    sales_error: null,
    held: 7,
    at_least: true,
    holdings: [{ character: "Holder", realm: "Realm", kind: "bags", units: 7 }],
    holdings_warning: "bank not captured",
    captures: [],
    farming: ["Alpha", "Beta"].map((name) => ({
      character: [name],
      farming: {
        rows: [
          {
            item_id: 2589,
            units: 3,
            units_per_hour: 36,
            value_per_hour_copper: null,
          },
        ],
        spots: [{ map_id: 1 }],
      },
    })),
    wowhead_url: "https://www.wowhead.com/forever/item=2589",
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, json: async () => data })),
  );
  host(
    <>
      <ItemActivity source="one" id={2589} />
      <ItemGathering source="one" id={2589} />
    </>,
  );
  expect(await screen.findByText(/4 of 5 sold/)).toBeTruthy();
  expect(screen.getByText(/at least 7 held/)).toBeTruthy();
  expect(screen.getByText("42c")).toBeTruthy();
  expect(screen.getByText("Alpha")).toBeTruthy();
  expect(screen.getByText("Beta")).toBeTruthy();
  expect(screen.getAllByText(/36 units\/hour/)).toHaveLength(2);
  expect(screen.getByText(/Your own past sessions/)).toBeTruthy();
});
it("opens Overview, exposes all record tabs and footer, reads selected identity in request", async () => {
  const requests: URL[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: URL) => {
      requests.push(url);
      return {
        ok: true,
        json: async () =>
          url.pathname.endsWith("activity")
            ? {
                farming: [],
                wowhead_url: "https://www.wowhead.com/forever/item=1",
              }
            : {
                item_id: 1,
                name: "Selected robe",
                quality: 2,
                price_copper: 999,
                typical_copper: null,
                units: 3,
                listings: 1,
                held: null,
                at_least: false,
                vendor_buy: [],
                vendor_sell: null,
                crowding: null,
                overshoot: null,
                used_in: { reason: "No compatible catalog recipe" },
                made_from: { reason: "No compatible catalog recipe" },
                details: { variant: '["variant","suffix"]' },
                evidence: {
                  freshness: null,
                  scan_id: "scan",
                  finished_at: "2026-10-16T00:00:00Z",
                  market_id: "forever",
                },
              },
      };
    }),
  );
  host(<ItemRecord source="one" id={1} variant={'["variant","suffix"]'} />);
  expect(await screen.findByText("Selected robe")).toBeTruthy();
  expect(
    screen.getByRole("tab", { name: "Overview" }).getAttribute("aria-selected"),
  ).toBe("true");
  expect(screen.getByRole("tab", { name: "Price history" })).toBeTruthy();
  expect(screen.getByRole("tab", { name: "Listings" })).toBeTruthy();
  expect(
    screen.getByRole("tab", { name: "Made from and used in" }),
  ).toBeTruthy();
  expect(screen.getByRole("tab", { name: "Our activity" })).toBeTruthy();
  expect(
    requests
      .find((r) => r.pathname.endsWith("/1"))
      ?.searchParams.get("variant"),
  ).toBe('["variant","suffix"]');
  expect(await screen.findByText("not gathered yet")).toBeTruthy();
  await userEvent.click(screen.getByText("Identity and evidence"));
  expect(screen.getAllByText(/"variant"/).length).toBeGreaterThan(0);
});
