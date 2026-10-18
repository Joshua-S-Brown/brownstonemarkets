import { render, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { Market, signalEvidence } from "./Market";
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
const row = (id: number, name: string, price: number | null): Row => ({
  item_id: id,
  name,
  price_copper: price,
  typical_copper: 300,
  beta_typical_copper: null,
  beta_ratio: null,
  beta_faded: true,
  gap_copper: price === null ? null : price - 300,
  gap_percent: price === null ? null : (price - 300) / 3,
  quality: 2,
  variant_state: "base",
  variant_id: null,
  roles: ["materials"],
  units: 20,
  listings: 10,
  signal: null,
  sparkline: [100, null, price],
  variants: [],
});
const rows = [
  {
    ...row(1, "Material", 90),
    signal,
    variants: [
      {
        ...row(1, "Material unresolved", 700),
        variant_state: "unresolved",
        units: 7,
      },
    ],
  },
  row(2, "Craft", 110),
];
const card = (id: number, name: string, sparkline = [100, 90]) => ({
  ...row(id, name, 90),
  sparkline,
  outside_chains: id === 5,
  removed_units: null,
});
afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});
it("keeps the signal evidence counts and unknown churn explanation", () => {
  expect(signalEvidence(signal)).toContain("2/3 comparable gaps");
  expect(
    signalEvidence({ ...signal, churn: { changed: 0, pairs: 0 } }),
  ).toContain("churn unknown");
});
it("renders head, three-plus-more cards, history threshold, separate collapsed identities and exact record links; delegates sorting and filters", async () => {
  sessionStorage.setItem("brownstone-team-one", "40");
  const user = userEvent.setup(),
    open = vi.fn();
  const fetch = vi.fn(async (...args: [URL | string]) => {
    expect(String(args[0])).toContain("source=one");
    return {
      ok: true,
      json: async () => ({
        rows,
        cards: {
          cheap: {
            preview: [
              card(1, "First"),
              card(2, "Second", [90]),
              card(3, "Third", []),
            ],
            more: [card(4, "Fourth"), card(5, "Outside")],
          },
          high: { preview: [], more: [] },
          early: {
            preview: [{ ...card(6, "Removed"), removed_units: 14 }],
            more: [],
          },
        },
        chain_count: 2290,
        listed_chain_count: 779,
        item_count: 2904,
        note: "Price caveat",
        warning: null,
        evidence: {
          scan_id: "scan-new",
          finished_at: "2026-10-17T10:42:01Z",
          freshness: { age_hours: 2.5, upstream_known: true },
        },
        movement: {},
        removals: {},
        floods: {},
      }),
    };
  });
  vi.stubGlobal("fetch", fetch);
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
  expect(String(fetch.mock.calls[0]?.[0])).toContain("role=levels");
  expect(String(fetch.mock.calls[0]?.[0])).toContain("window=40");
  expect(screen.getByText(/next 40 points/)).toBeTruthy();
  expect(screen.getAllByText("base").length).toBeGreaterThan(0);
  expect(
    screen
      .getByRole("button", { name: "For our levels" })
      .getAttribute("aria-pressed"),
  ).toBe("true");
  await user.click(screen.getByRole("button", { name: "All in our chains" }));
  await waitFor(() =>
    expect(String(fetch.mock.calls.at(-1)?.[0])).toContain("role=all"),
  );
  expect(screen.getByText(/779 listed now of 2,290 items/)).toBeTruthy();
  expect(screen.getByText(/2,904 items · 2.5h old/)).toBeTruthy();
  expect(screen.getAllByText(/Listings are supply, not sales/)).toHaveLength(1);
  // Snapshot notes and warnings stay on the page, not inside the collapsed evidence footer.
  expect(screen.getByText("Price caveat").closest("details")).toBeNull();
  expect(
    screen.getByText(/bought or cancelled; an upper bound on sales/),
  ).toBeTruthy();
  expect(screen.getByText("14 units")).toBeTruthy();
  expect(
    screen.getByRole("img", { name: "First stored lowest buyout" }),
  ).toBeTruthy();
  expect(
    screen.queryByRole("img", { name: "Second stored lowest buyout" }),
  ).toBeNull();
  expect(
    screen.queryByRole("img", { name: "Third stored lowest buyout" }),
  ).toBeNull();
  const more = screen.getByText("2 more");
  expect(more.parentElement!.hasAttribute("open")).toBe(false);
  await user.click(more);
  expect(more.parentElement!.hasAttribute("open")).toBe(true);
  expect(screen.getByText(/Outside our chains/)).toBeTruthy();
  let body = screen.getByRole("table").querySelector("tbody")!;
  expect(within(body).getAllByRole("row")).toHaveLength(2);
  expect(
    within(body).getAllByRole("row")[0]!.getAttribute("data-selected"),
  ).toBe("true");
  await user.click(
    screen.getByRole("button", { name: "+1 variants/unresolved" }),
  );
  expect(within(body).getAllByRole("row")).toHaveLength(3);
  expect(within(body).getAllByRole("row")[1]!.textContent).toContain("7");
  await user.click(
    within(body).getByRole("button", { name: "Material unresolved" }),
  );
  expect(open).toHaveBeenLastCalledWith({
    item: 1,
    variant: '["unresolved",null]',
  });
  await user.click(within(body).getByRole("button", { name: "Material" }));
  expect(open).toHaveBeenLastCalledWith({ item: 1, variant: '["base",null]' });
  await user.click(screen.getByRole("button", { name: "Lowest" }));
  await waitFor(() =>
    expect(String(fetch.mock.calls.at(-1)?.[0])).toContain("sort=price_copper"),
  );
  // The response order remains authoritative even if it contradicts the chosen column.
  body = screen.getByRole("table").querySelector("tbody")!;
  expect(within(body).getAllByRole("row")[0]!.textContent).toContain(
    "Material",
  );
  await user.click(
    screen.getByRole("button", { name: "Crafts and intermediates" }),
  );
  await waitFor(() =>
    expect(String(fetch.mock.calls.at(-1)?.[0])).toContain("role=crafts"),
  );
  await user.type(
    screen.getByLabelText("Search snapshot by name or ID"),
    "2589",
  );
  await waitFor(() =>
    expect(String(fetch.mock.calls.at(-1)?.[0])).toContain("q=2589"),
  );
});

it.each(["shown", "missing", "faded", "unconfigured"])(
  "shows beta reference only before live history: %s",
  async (state) => {
    const reference = {
      source_id: "beta",
      label: "Frozen beta",
      market_id: "forever-us-normal-alliance-beta",
      newest_scan: "2026-10-17T10:42:01Z",
    };
    const r = {
      ...row(1, "Material", state === "missing" ? null : 90),
      typical_copper: state === "faded" ? 100 : null,
      beta_faded: state === "faded",
      beta_typical_copper: state === "shown" ? 300 : null,
      beta_ratio:
        state === "shown" ? { numerator: 90, denominator: 300 } : null,
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          rows: [r],
          reference: state === "unconfigured" ? null : reference,
          cards: Object.fromEntries(
            ["cheap", "high", "early"].map((k) => [
              k,
              { preview: [], more: [] },
            ]),
          ),
          chain_count: 1,
          listed_chain_count: 1,
          item_count: 1,
          evidence: {},
          note: "",
          warning: null,
        }),
      })),
    );
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <Market source="one" />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await screen.findByRole("table");
    if (state === "shown" || state === "missing") {
      expect(
        screen.getByRole("columnheader", { name: "Beta typical" }),
      ).toBeTruthy();
      if (state === "shown") {
        expect(
          screen.getByText("30.0% of beta", { exact: false }),
        ).toBeTruthy();
        await userEvent.hover(
          screen.getByText("30.0% of beta", { exact: false }),
        );
        expect(await screen.findByRole("tooltip")).toHaveProperty(
          "textContent",
          expect.stringContaining(
            "beta reference, a different market · Frozen beta · newest scan 17 Oct 10:42 UTC",
          ),
        );
      } else {
        expect(screen.getByText(/no beta price/)).toBeTruthy();
        expect(screen.getByText(/no live price/)).toBeTruthy();
      }
    } else {
      expect(
        screen.queryByRole("columnheader", { name: "Beta typical" }),
      ).toBeNull();
    }
  },
);
