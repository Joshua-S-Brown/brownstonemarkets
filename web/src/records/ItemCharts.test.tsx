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
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  ComposedChart: () => null,
  LineChart: () => null,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  CartesianGrid: () => null,
}));
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
it("shows three qualifying removal gaps, skipped count, and expands the rest", async () => {
  const pair = {
    skipped: false,
    earlier: { finished_at: "2026-10-15T00:00:00Z" },
    later: { finished_at: "2026-10-15T01:00:00Z" },
    gap: 3600,
    items: [],
  };
  host(
    <RemovalHistory
      h={{
        ...h,
        removals: {
          note: "",
          pairs: [pair, { ...pair, skipped: true }, pair, pair, pair, pair],
        },
      }}
    />,
  );
  expect(screen.getByText("1 skipped gaps (over 12 hours)")).toBeTruthy();
  expect(screen.getAllByText("Gap 1.00 hours")).toHaveLength(3);
  await userEvent.click(
    screen.getByRole("button", { name: "Show all scan gaps" }),
  );
  expect(screen.getAllByText("Gap 1.00 hours")).toHaveLength(5);
});
