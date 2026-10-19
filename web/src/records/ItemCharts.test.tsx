import { CharacterHistory } from "./CharacterHistory";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import {
  historyData,
  ItemCharts,
  LadderPanel,
  RemovalHistory,
} from "./ItemCharts";
import type { History } from "../api/market";
vi.mock("recharts", async (original) => {
  const actual = await original<typeof import("recharts")>();
  const { cloneElement } = await import("react");
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactElement }) =>
      cloneElement(
        children as React.ReactElement<{ width: number; height: number }>,
        { width: 440, height: 300 },
      ),
  };
});
afterEach(() => vi.unstubAllGlobals());
const h: History = {
  scans: [
    { scan_id: "new", finished_at: "2026-10-16T12:00:00Z" },
    { scan_id: "old", finished_at: "2026-10-15T12:00:00Z" },
  ],
  points: [
    {
      scan_id: "old",
      finished_at: "2026-10-15T12:00:00Z",
      metrics: { min_buyout: 123, market_value: 456, units: 3 },
    },
    { scan_id: "gap", finished_at: "2026-10-16T00:00:00Z", metrics: null },
    {
      scan_id: "new",
      finished_at: "2026-10-16T12:00:00Z",
      metrics: { min_buyout: null, market_value: null, units: 7 },
    },
  ],
  other_identities: 1,
  note: "",
  removals: { note: "", pairs: [] },
  removals_error: null,
};
function host(ui: React.ReactNode) {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      {ui}
    </QueryClientProvider>,
  );
}
it("uses continuous finish times, retains absent gaps and null prices with visible supply", () => {
  const d = historyData(h);
  expect(d.map((p) => p.lowest)).toEqual([123, null, null]);
  expect(d.map((p) => p.units)).toEqual([3, null, 7]);
  expect(d[2]!.time - d[0]!.time).toBe(24 * 3600000);
  expect(d[0]!.scan).toBe("old");
});
it("defaults to newest ladder, picks an older scan, retains every price level and 95% zoom", async () => {
  const requests: string[] = [];
  const user = userEvent.setup();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: URL) => {
      requests.push(url.toString());
      return {
        ok: true,
        json: async () =>
          url.pathname.endsWith("history")
            ? h
            : {
                rows: [
                  {
                    price_copper: 20,
                    listings: 1,
                    units: 90,
                    cumulative_units: 90,
                  },
                  {
                    price_copper: 25,
                    listings: 1,
                    units: 6,
                    cumulative_units: 96,
                  },
                  {
                    price_copper: 500000,
                    listings: 1,
                    units: 4,
                    cumulative_units: 100,
                  },
                ],
                no_buyout_listings: 2,
                no_buyout_units: 7,
                note: "",
                freshness: { age_hours: 2, stale: true },
                zoom_copper: 25,
              },
      };
    }),
  );
  host(<ItemCharts source="one" id={2589} listings />);
  await screen.findByText("3 buyout listings · 100 units · 3 price levels");
  expect(
    (screen.getByLabelText("Highest displayed ask") as HTMLInputElement).value,
  ).toBe("25");
  expect(screen.getByText("50g")).toBeTruthy();
  expect(
    screen.getByText(/Without a buyout: 2 listings · 7 units/),
  ).toBeTruthy();
  expect(screen.getByText(/1 other newest identities excluded/)).toBeTruthy();
  expect(
    requests.some((r) => r.includes("scan=new") && r.includes("source=one")),
  ).toBe(true);
  await user.selectOptions(screen.getByLabelText("Ladder scan"), "old");
  await screen.findByText("3 buyout listings · 100 units · 3 price levels");
  expect(requests.some((r) => r.includes("scan=old"))).toBe(true);
});
it("gives local read-error guidance and one-scan/empty guidance", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: false,
      json: async () => ({
        detail: "Read failed. Use Data, then reopen this item.",
      }),
    })),
  );
  host(<LadderPanel source="one" id={1} scan="foreign" />);
  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    expect.stringContaining("Use Data"),
  );
});
it("summarises removals per identity over comparable gaps, with each gap on demand", async () => {
  const counts = (early: number, expiry: number) => ({
    early: { listings: early, units: early * 2 },
    expiry: { listings: expiry, units: expiry * 2 },
    unknown: { listings: 0, units: 0 },
    without_buyout: { earlier: 0, later: 0 },
    evidence: [],
  });
  const identity = { item_id: 1, item_name: "Robe", variant_id: null };
  const pair = {
    skipped: false,
    earlier: { finished_at: "2026-10-15T00:00:00Z" },
    later: { finished_at: "2026-10-15T01:00:00Z" },
    gap: 3600,
    items: [
      { ...identity, variant_state: "base", ...counts(1, 2) },
      { ...identity, variant_state: "variant", ...counts(300, 0) },
    ],
  };
  host(
    <RemovalHistory
      h={{
        ...h,
        removals: {
          note: "",
          pairs: [pair, { ...pair, skipped: true }, pair, pair],
        },
      }}
    />,
  );
  expect(
    screen.getByText("3 comparable gaps · 1 skipped gaps (over 12 hours)"),
  ).toBeTruthy();
  const totals = screen.getAllByText(/Removed early: .* Could have expired/);
  expect(totals.map((p) => p.textContent!.trim())).toEqual([
    "Removed early: 3 listings · 6 units · Could have expired: 6 listings · 12 units",
    "variant Removed early: 900 listings · 1,800 units · Could have expired: 0 listings · 0 units",
  ]);
  const gaps = screen.getAllByText(/gap 1.00 hours/);
  expect(gaps).toHaveLength(3);
  expect(gaps[0]!.closest("details")!.hasAttribute("open")).toBe(false);
  await userEvent.click(gaps[0]!);
  expect(gaps[0]!.closest("details")!.hasAttribute("open")).toBe(true);
  expect(
    screen.getAllByText("Removed early: 300 listings · 600 units"),
  ).toHaveLength(3);
});

it("renders distinct chart series, labelled axes, UTC ticks and a dashed typical reference", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, json: async () => h })),
  );
  const { container, unmount } = host(<ItemCharts source="one" id={2589} />);
  await screen.findByText("Unit price");
  expect(screen.getAllByText("Units listed").length).toBeGreaterThan(0);
  const colors = [...container.querySelectorAll(".recharts-legend-item")].map(
    (item) =>
      item.querySelector(".recharts-legend-item-text")?.getAttribute("style"),
  );
  expect(colors).toHaveLength(3);
  expect(new Set(colors).size).toBe(3);
  expect(container.textContent).toContain("15 Oct");
  expect(container.textContent).not.toMatch(/\d{4}-\d\d-\d\dT\d\d:/);
  unmount();
  const overview = host(
    <ItemCharts source="one" id={2589} overview typical={200} />,
  );
  await screen.findByText("Typical");
  expect(
    overview.container
      .querySelector(".recharts-reference-line line")
      ?.getAttribute("stroke-dasharray"),
  ).toBe("5 4");
  overview.unmount();
  const character = host(
    <CharacterHistory
      rows={[
        { UTC: "2026-10-16T12:00:00Z", Series: "Level", Value: 8, Sequence: 2 },
        {
          UTC: "2026-10-16T12:00:00Z",
          Series: "Mining",
          Value: 48,
          Sequence: 2,
        },
      ]}
    />,
  );
  const strokes = [
    ...character.container.querySelectorAll(".recharts-legend-item-text"),
  ].map((p) => p.getAttribute("style"));
  expect(new Set(strokes).size).toBe(2);
  expect(screen.getByText("All readings")).toBeTruthy();
  expect(screen.queryByRole("columnheader", { name: "Sequence" })).toBeNull();
  expect(character.container.textContent).not.toMatch(/\d{4}-\d\d-\d\dT\d\d:/);
});
