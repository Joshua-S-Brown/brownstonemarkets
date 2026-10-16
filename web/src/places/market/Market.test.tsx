import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { Market, chainListed, filterRows, signalEvidence } from "./Market";
import { InspectorContext } from "../../app/InspectorContext";
import type { Row, Signal } from "../../api/market";
const signal: Signal = {
  item_id: 1,
  item_name: "Material",
  variant_id: null,
  variant_state: "base",
  crowding: "contested",
  listings: 10,
  units: 20,
  largest_stack_units: 10,
  churn: { changed: 2, pairs: 3 },
  overshoot: {
    label: "cheap",
    typical_copper: 300,
    days: 3,
    scans: 5,
    ratio: { numerator: 90, denominator: 300 },
  },
};
const row = (
  id: number,
  name: string,
  price: number | null,
  roles: string[],
): Row => ({
  item_id: id,
  name,
  price_copper: price,
  typical_copper: 300,
  gap_copper: price === null ? null : price - 300,
  gap_percent: price === null ? null : (price - 300) / 3,
  quality: 2,
  variant_state: "base",
  variant_id: null,
  roles,
  units: 20,
  listings: 10,
  signal: null,
  sparkline: [100, null, price],
});
const rows = [
  { ...row(1, "Material", 90, ["materials"]), signal },
  row(2, "Craft", 110, ["crafts"]),
  row(3, "Intermediate", null, ["materials", "crafts", "intermediates"]),
  row(4, "Outside material name", null, []),
];
afterEach(() => vi.unstubAllGlobals());
it("filters by catalog membership and searches every snapshot item, keeping missing prices unknown", () => {
  expect(filterRows(rows, "materials", "").map((r) => r.item_id)).toEqual([
    1, 3,
  ]);
  expect(filterRows(rows, "intermediates", "").map((r) => r.item_id)).toEqual([
    3,
  ]);
  expect(filterRows(rows, "signal", "").map((r) => r.item_id)).toEqual([1]);
  expect(filterRows(rows, "all", "outside").map((r) => r.item_id)).toEqual([4]);
  expect(filterRows(rows, "all", "4")[0]!.price_copper).toBeNull();
  expect(
    chainListed([
      ...rows,
      { ...row(1, "Material", 90, ["materials"]), variant_state: "unresolved" },
    ]),
  ).toBe(3);
  expect(signalEvidence(signal)).toContain("2/3 comparable gaps");
  expect(
    signalEvidence({ ...signal, churn: { changed: 0, pairs: 0 } }),
  ).toContain("churn unknown");
});
it("renders pulse, sorts in copper, retains selected identity, opens exact record and changes role chips", async () => {
  const user = userEvent.setup(),
    open = vi.fn();
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        rows,
        pulse: { cheap: [signal], high: [], early: [] },
        chain_count: 3,
        note: "",
        warning: null,
        evidence: {},
        movement: {},
        removals: {},
        floods: {},
      }),
    })),
  );
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter
        initialEntries={[
          "/?source=one&inspect=1&variant=" +
            encodeURIComponent('["base",null]'),
        ]}
      >
        <InspectorContext.Provider value={open}>
          <Market source="one" />
        </InspectorContext.Provider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  await screen.findByRole("heading", { name: "Cheaper than usual" });
  expect(screen.getByText(/upper bound on purchases/)).toBeTruthy();
  expect(
    screen.getByText(/3 listed now of 3 items in our chains/),
  ).toBeTruthy();
  await user.click(screen.getByRole("button", { name: "Lowest / unit" }));
  const body = screen.getByRole("table").querySelector("tbody")!;
  const visible = within(body).getAllByRole("row");
  expect(visible[0]!.textContent).toContain("Material");
  expect(visible[1]!.textContent).toContain("Craft");
  expect(visible[0]!.getAttribute("data-selected")).toBe("true");
  await user.click(within(body).getByRole("button", { name: "Material" }));
  expect(open).toHaveBeenCalledWith({ item: 1, variant: '["base",null]' });
  await user.click(screen.getByRole("button", { name: "Intermediates" }));
  expect(
    within(screen.getByRole("table")).getByText("Intermediate"),
  ).toBeTruthy();
  expect(within(screen.getByRole("table")).queryByText("Craft")).toBeNull();
  await user.type(screen.getByLabelText("Search snapshot by name or ID"), "4");
  expect(
    within(screen.getByRole("table")).getByText("Outside material name"),
  ).toBeTruthy();
  expect(
    within(screen.getByRole("table")).getAllByText("—").length,
  ).toBeGreaterThan(0);
});
