import { RemovalSpeed } from "../ui/RemovalSpeed";
import { render, screen, within } from "@testing-library/react";
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
        used_in: [
          {
            ...recipe,
            quantity: 1,
            profession: "tailoring",
            profit_copper: 123,
          },
          { ...recipe, profit_copper: 123 },
        ],
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
  expect(screen.getAllByText("Team: Unknown")).toHaveLength(3);
  expect(screen.getByText("1 unit per craft")).toBeTruthy();
  expect(screen.getByText("22c")).toBeTruthy();
  expect(screen.getByText("Tailoring: 1–45")).toBeTruthy();
  expect(
    screen
      .getAllByRole("link", { name: "Open in Supply chains" })[0]
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
        spots: [
          {
            map_id: 1,
            npc_id: 20,
            mob: "Kobold (NPC 20)",
            mob_name: "Kobold",
            also_looted_labels: ["NPC 30"],
            also_looted_names: [null],
          },
        ],
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
  expect(screen.getAllByRole("link", { name: "Kobold" })).toHaveLength(2);
  expect(screen.getAllByText(/also looted: Unknown creature/)).toHaveLength(2);
  expect(screen.getByText(/Your own past sessions/)).toBeTruthy();
});
function stubRecord(held: number | null) {
  const requests: URL[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: URL) => {
      requests.push(url);
      return {
        ok: true,
        json: async () =>
          url.pathname.endsWith("history")
            ? { points: [], scans: [], other_identities: 0, note: "" }
            : url.pathname.endsWith("activity")
              ? {
                  farming: [],
                  holdings: [
                    {
                      character: "Basilly",
                      realm: "R",
                      kind: "bags",
                      units: 22,
                    },
                    {
                      character: "Keenagen",
                      realm: "R",
                      kind: "bank",
                      units: 14,
                    },
                  ],
                  wowhead_url: "https://www.wowhead.com/forever/item=1",
                }
              : {
                  speed: {
                    label:
                      "removed early (upper bound on sales; includes cancels and reposts)",
                    pairs: 3,
                    hours: 4,
                    daily_units: null,
                    median_units: 1,
                    days_supply: null,
                    suggested_units: null,
                    reason: "not enough scan gaps (3, 4.0 h)",
                    settings: {
                      speed_window_days: 14,
                      speed_min_pairs: 5,
                      speed_min_hours: 24,
                      speed_cover_days: 3,
                      speed_cap_percent: 25,
                    },
                  },
                  role: "Craft",
                  deposit_copper: 100,
                  item_id: 1,
                  name: "Selected robe",
                  quality: 2,
                  price_copper: 999,
                  typical_copper: null,
                  units: 3,
                  listings: 1,
                  held,
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
  return requests;
}
it("opens Overview, exposes all record tabs and footer, reads selected identity in request", async () => {
  const requests = stubRecord(null);
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
  expect(
    (await screen.findAllByText(/not gathered yet/)).length,
  ).toBeGreaterThan(0);
  expect(screen.getByText("not enough scan gaps (3, 4.0 h)")).toBeTruthy();
  expect(
    screen.getByText(/upper bound on sales; includes cancels and reposts/),
  ).toBeTruthy();
  const facts = screen.getByLabelText("Item facts");
  expect(facts.textContent).toContain(
    "Lowest9s 99cTypical—Listings · units1 · 3",
  );
  const header = screen.getByRole("heading", {
    name: "Selected robe",
  }).parentElement!;
  expect(header.textContent).toContain("Craft · 1 · variant");
  expect(header.textContent).not.toContain("Overview");
  expect(document.body.textContent).not.toContain("Basilly");
  await userEvent.click(screen.getByRole("tab", { name: "Price history" }));
  expect(header.textContent).not.toContain("Price history");
  expect(within(facts).getByText("Lowest")).toBeTruthy();
  expect(document.body.textContent).not.toMatch(/\d{4}-\d\d-\d\dT\d\d:/);
  await userEvent.click(screen.getByText("Identity and evidence"));
  expect(screen.getAllByText(/"variant"/).length).toBeGreaterThan(0);
});
it("lists each base-item holder beside team holdings, but not on a variant", async () => {
  stubRecord(36);
  host(<ItemRecord source="one" id={1} />);
  expect(
    await screen.findByText(/36 units · Basilly 22, Keenagen bank 14/),
  ).toBeTruthy();
});

it("shows zero removal evidence without numeric turnover and leaves insufficient suggestions blank", () => {
  const evidence = {
    label: "removed early (upper bound on sales; includes cancels and reposts)",
    pairs: 5,
    hours: 24,
    daily_units: 0,
    median_units: 10,
    days_supply: null,
    suggested_units: 0,
    reason: "no early removals in 5 scan gaps",
    settings: {
      speed_window_days: 14,
      speed_min_pairs: 5,
      speed_min_hours: 24,
      speed_cover_days: 3,
      speed_cap_percent: 25,
    },
  };
  const rendered = render(<RemovalSpeed speed={evidence} suggested />);
  expect(screen.getByText("no early removals in 5 scan gaps")).toBeTruthy();
  expect(screen.queryByText(/days of listed supply/)).toBeNull();
  expect(screen.getByText("Suggested: 0 units")).toBeTruthy();
  rendered.rerender(
    <RemovalSpeed
      speed={{
        ...evidence,
        daily_units: null,
        suggested_units: null,
        reason: "not enough scan gaps (4, 24.0 h)",
      }}
      suggested
    />,
  );
  expect(screen.getByText("Suggested: — units")).toBeTruthy();
  expect(screen.getByText("not enough scan gaps (4, 24.0 h)")).toBeTruthy();
});
