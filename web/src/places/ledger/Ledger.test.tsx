import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import { Ledger } from "./Ledger";
import { InspectorContext } from "../../app/InspectorContext";
import { readDays, writeDays } from "./state";
vi.mock("./Chart", () => ({ Chart: () => <p>Daily chart</p> }));
const entry = {
  item_id: 2589,
  target_units: 20,
  buy_copper: 30,
  buy_percent: null,
};
const payload = {
  evidence: { source_id: "one", market_id: "market" },
  errors: {},
  names: { 2589: "Linen Cloth" },
  gold: {
    team: { in_copper: 1023, out_copper: 10, net_copper: 1013 },
    pairs: { reconciled: 1, total: 2, unknown: 1 },
    movement_count: 3,
    daily: [],
    categories: [],
    totals: [
      {
        character: ["Maker", "Realm", "Alliance"],
        day: "2026-10-16",
        category: "auction sale",
        in_copper: 1023,
        out_copper: 0,
      },
    ],
    reconciliation: [],
    evidence: { ledger_version: 1 },
  },
  items: {
    team: { in_units: 2, out_units: 1 },
    movement_count: 2,
    totals: [],
    transfers: [
      {
        sender: ["Maker", "Realm", "Alliance"],
        recipient: ["Bob", "Realm", "Alliance"],
        item_id: 2589,
        units: 1,
        status: "sent, not yet received",
      },
    ],
    pairs: [],
    reconciliation: [],
    evidence: {},
  },
  stock: {
    scan_state: "Stale",
    entries: [entry],
    names: { 2589: "Linen Cloth" },
    captures: [
      {
        character: "Cara",
        kind: "bank",
        unknown: true,
        empty: false,
        partial: false,
        excluded: 1,
      },
    ],
    items_held: 1,
    value_copper: 220,
    excluded_prices: 1,
    items_short: 1,
    buy_cost_copper: 200,
    rows: [
      {
        item_id: 2589,
        name: "Linen Cloth",
        variant_id: null,
        variant_state: "base",
        held: 11,
        target_units: 20,
        short: 9,
        at_most: true,
        buy_units: 9,
        wait_units: 0,
        unlisted_units: 0,
        buy_cost_copper: 200,
        fill_cost_copper: 200,
        value_copper: 220,
        entry,
        fill_state: "priced",
      },
    ],
    holdings: [],
    evidence: { snapshot: { scan_id: "scan" } },
  },
};
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});
function mount() {
  const inspect = vi.fn();
  const calls: { url: URL; body: Record<string, unknown> | null }[] = [];
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: URL, options?: RequestInit) => {
      const body = options?.body ? JSON.parse(String(options.body)) : null;
      calls.push({ url, body });
      return {
        ok: true,
        json: async () =>
          url.pathname.endsWith("/movements")
            ? [
                {
                  entry_id: "entry",
                  machine: "pc",
                  copper: 268,
                  parts: [{ category: "auction sale", copper: 268 }],
                  ledger_version: 1,
                },
              ]
            : payload,
      };
    }),
  );
  render(
    <QueryClientProvider client={client}>
      <InspectorContext.Provider value={inspect}>
        <Ledger source="one" />
      </InspectorContext.Provider>
    </QueryClientProvider>,
  );
  return { inspect, calls, invalidate };
}
it("persists days per source, sends shared filters and loads category provenance only on demand", async () => {
  const user = userEvent.setup();
  const { calls, inspect } = mount();
  await screen.findByText("3 recorded changes");
  expect(calls.some((c) => c.url.pathname.endsWith("/movements"))).toBe(false);
  await user.selectOptions(screen.getByLabelText("Days"), "all");
  expect(readDays("one")).toBe("all");
  expect(readDays("two")).toBe("7");
  await user.type(screen.getByLabelText("Name or item ID"), "2589");
  await user.click(screen.getByLabelText("Our catalog chains only"));
  await waitFor(() =>
    expect(
      calls.some(
        (c) =>
          c.url.searchParams.get("q") === "2589" &&
          c.url.searchParams.get("chains") === "true",
      ),
    ).toBe(true),
  );
  await user.click(screen.getByRole("button", { name: "auction sale" }));
  await screen.findByText("entry");
  expect(
    calls.filter((c) => c.url.pathname.endsWith("/movements")),
  ).toHaveLength(1);
  await user.click(screen.getAllByRole("button", { name: "Maker" })[0]);
  expect(inspect).toHaveBeenCalledWith({
    character: ["Maker", "Realm", "Alliance"],
  });
  await user.click(screen.getByRole("button", { name: "Bob" }));
  expect(inspect).toHaveBeenLastCalledWith({
    character: ["Bob", "Realm", "Alliance"],
  });
  await user.click(screen.getAllByRole("button", { name: "Linen Cloth" })[0]);
  expect(inspect).toHaveBeenLastCalledWith({ item: 2589 });
  await user.click(screen.getAllByRole("button", { name: "Linen Cloth" })[1]);
  expect(inspect).toHaveBeenLastCalledWith({
    item: 2589,
    variant: '["base",null]',
  });
  expect(screen.getByText("at most 9")).toBeTruthy();
  expect(screen.getByText(/unreadable capture/)).toBeTruthy();
});
it("targets use fresh drafts, validation, Remove and Save only; success invalidates Ledger", async () => {
  const user = userEvent.setup();
  const { calls, invalidate } = mount();
  await screen.findByText("3 recorded changes");
  await user.click(screen.getByRole("button", { name: "Set stock targets" }));
  let dialog = screen.getByRole("dialog");
  await user.type(within(dialog).getByLabelText("Item ID"), "2589");
  await user.type(within(dialog).getByLabelText("Target units"), "bad");
  await user.click(
    within(dialog).getByRole("button", { name: "Update draft" }),
  );
  expect(screen.getByText(/Draft rejected/)).toBeTruthy();
  await user.clear(within(dialog).getByLabelText("Target units"));
  await user.type(within(dialog).getByLabelText("Target units"), "30");
  await user.click(
    within(dialog).getByRole("button", { name: "Update draft" }),
  );
  expect(calls.some((c) => c.body)).toBe(false);
  await user.click(within(dialog).getByRole("button", { name: "Close ✕" }));
  await user.click(screen.getByRole("button", { name: "Set stock targets" }));
  dialog = screen.getByRole("dialog");
  expect(within(dialog).getByText(/20 units/)).toBeTruthy();
  await user.click(
    within(dialog).getByRole("button", { name: "Remove target from draft" }),
  );
  expect(screen.getByText(/Enter an item ID/)).toBeTruthy();
  await user.type(within(dialog).getByLabelText("Item ID"), "2589");
  await user.click(
    within(dialog).getByRole("button", { name: "Remove target from draft" }),
  );
  expect(within(dialog).queryByText(/20 units/)).toBeNull();
  await user.click(
    within(dialog).getByRole("button", { name: "Save targets" }),
  );
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(calls.find((c) => c.body)?.body).toEqual({ entries: [] });
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["one", "ledger"] });
});
it("tolerates bad or blocked session storage", () => {
  sessionStorage.setItem("brownstone-ledger-one", "bad");
  expect(readDays("one")).toBe("7");
  const spy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw Error("blocked");
  });
  writeDays("one", "30");
  spy.mockRestore();
});

it("renders short character names without the full identity in page text", async () => {
  mount();
  await screen.findAllByRole("button", { name: "Maker" });
  expect(document.body.textContent).not.toMatch(
    /(?:Maker|Basilly) · (?:Realm(?: [12])?|Beta) · Alliance/,
  );
});
