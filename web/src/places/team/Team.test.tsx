import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Team } from "./Team";
import { Path, Steps } from "./Path";
import { Hire, HireDetail } from "./Hiring";
import { InspectorContext } from "../../app/InspectorContext";
import { readWindow, writeWindow } from "./state";
import type { Group, TeamData } from "./types";
const estimate = {
  complete: false,
  cost_copper: null,
  reasons: ["training cost unknown"],
  steps: [
    {
      rank: 1,
      recipe: "A",
      expected_crafts: "1",
      cost_copper: 10000,
      training_cost_copper: 101,
    },
    {
      rank: 2,
      recipe: "B",
      expected_crafts: "1",
      cost_copper: 200,
      training_cost_copper: null,
    },
  ],
};
const recipe = {
  name: "Raptor Bites",
  output_item_id: 10,
  required_skill: 10,
  points_needed: 2,
  profit_copper: 194,
  training_cost_copper: 100,
  estimate,
  learn_from: "drop",
  payback: { status: "crafts" as const, crafts: 1 },
};
const group: Group = {
  profession: "Cooking",
  rank: 2,
  max_rank: 75,
  recipes: [recipe],
  best: recipe,
  alternative: {
    ...recipe,
    name: "Wolf Meat",
    profit_copper: -45,
    learn_from: "trainer",
  },
  alternative_kind: "learn",
  gathering: false,
  next_step: "best",
  note: "",
};
const row = { profession: "tailoring", holders: [], best: null, estimate };
const detail = {
  profession: "tailoring",
  needs_pattern: 1,
  unknown_source: 2,
  tiers: [
    {
      cap: 75,
      required_level: 10,
      tier_fees: "tier fees not included (unknown)",
      estimate,
      best: null,
      feeds: {
        count: 1,
        top: [
          { material: "Copper Bar", recipe: "Craft 20", saved_copper: 270 },
        ],
      },
    },
  ],
};
function fixture(): TeamData {
  return {
    roster: [1, 2].map((i) => ({
      character: ["Maker", "Realm " + i, "Alliance"],
      card: {
        name: "Maker",
        realm: "Realm " + i,
        faction: "Alliance",
        machine: null,
        last_seen_relative: "unknown",
        last_seen_utc: "unknown",
        level: null,
        gold_copper: null,
        stale: false,
        skills_status: "unknown",
        professions: [
          {
            name: "Cooking",
            rank: null,
            max_rank: null,
            at_cap: false,
            known_count: null,
            recipe_source: "unknown",
            recipes_at: "unknown",
            possibly_incomplete: true,
            seen_at: null,
          },
        ],
        history: [],
      },
      progression: { professions: [group] },
    })),
    hires: [row],
    no_catalog: ["fishing"],
    comparisons: [],
    all_incomplete: true,
    notes: [],
    evidence: { source_id: "one", market_id: "market", freshness: null },
    labels: "Current-scan profit, not a forecast",
    hiring_labels: "listings never sales",
  };
}
const open = vi.fn();
const requests: URL[] = [];
beforeEach(() => {
  sessionStorage.clear();
  requests.length = 0;
  open.mockClear();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: URL) => {
      requests.push(url);
      return {
        ok: true,
        json: async () =>
          url.pathname.includes("/hire/") ? detail : fixture(),
      };
    }),
  );
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
function wrap(child: React.ReactNode) {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <InspectorContext.Provider value={open}>
        {child}
      </InspectorContext.Provider>
    </QueryClientProvider>,
  );
}
it("keeps windows per tab/source, commits only on release, and opens exact same-name identities", async () => {
  writeWindow("other", 45);
  const view = wrap(<Team source="one" />);
  await screen.findByRole("button", { name: "Maker · Realm 1" });
  expect(requests.filter((r) => r.pathname === "/api/team")).toHaveLength(1);
  expect(requests.some((r) => r.pathname.includes("/hire/"))).toBe(false);
  fireEvent.change(screen.getByRole("slider"), { target: { value: "30" } });
  expect(requests.filter((r) => r.pathname === "/api/team")).toHaveLength(1);
  fireEvent.pointerUp(screen.getByRole("slider"));
  await waitFor(() =>
    expect(requests.at(-1)?.searchParams.get("window")).toBe("30"),
  );
  expect(readWindow("one")).toBe(30);
  expect(readWindow("other")).toBe(45);
  await userEvent.click(
    await screen.findByRole("button", { name: "Maker · Realm 1" }),
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Maker · Realm 2" }),
  );
  expect(open.mock.calls.map((c) => c[0])).toEqual([
    { character: ["Maker", "Realm 1", "Alliance"] },
    { character: ["Maker", "Realm 2", "Alliance"] },
  ]);
  expect(screen.getAllByText(/Level unknown/)).toHaveLength(2);
  expect(
    screen.getByText(
      "Cost to 300 is incomplete for every profession; open one to see why",
    ),
  ).toBeTruthy();
  expect(screen.queryByText(/cost to 300: incomplete/)).toBeNull();
  view.unmount();
  wrap(<Team source="one" />);
  expect((screen.getByRole("slider") as HTMLInputElement).value).toBe("30");
  sessionStorage.setItem("brownstone-team-one", "101");
  expect(readWindow("one")).toBe(25);
  sessionStorage.setItem("brownstone-team-one", "{");
  expect(readWindow("one")).toBe(25);
});
it("loads hire detail only on first opening and retains it when reopened", async () => {
  wrap(<Hire row={row} source="one" showCost />);
  expect(requests).toHaveLength(0);
  const disclosure = screen
    .getByText(/Tailoring · best at 300/)
    .closest("details")!;
  (disclosure as HTMLDetailsElement).open = true;
  fireEvent(disclosure, new Event("toggle"));
  await screen.findByText(/New hire: rank 1/);
  expect(requests).toHaveLength(1);
  (disclosure as HTMLDetailsElement).open = false;
  fireEvent(disclosure, new Event("toggle"));
  (disclosure as HTMLDetailsElement).open = true;
  fireEvent(disclosure, new Event("toggle"));
  await waitFor(() => expect(requests).toHaveLength(1));
  expect(screen.getByText(/Copper Bar → Craft 20/).textContent).toContain("2");
  expect(
    screen.getAllByText("tier fees not included (unknown)").length,
  ).toBeGreaterThan(0);
});
it("retains alternatives, learning columns, gathering IDs and empty catalog sentences", () => {
  const view = wrap(<Path groups={[group]} window={25} />);
  expect(screen.getByText("Or learn now")).toBeTruthy();
  expect(
    screen.getByText("reliable while you look for the pattern"),
  ).toBeTruthy();
  expect(screen.getByRole("button", { name: /Learn from/ })).toBeTruthy();
  expect(
    screen.getAllByText("pays back training in 1 crafts", { exact: false })
      .length,
  ).toBeGreaterThan(0);
  view.unmount();
  wrap(
    <Path
      groups={[
        {
          ...group,
          best: null,
          alternative: null,
          recipes: [],
          profession: "Arbitrary title",
          gathering: true,
        },
        {
          ...group,
          best: null,
          alternative: null,
          recipes: [],
          profession: "Mining",
          gathering: false,
        },
      ]}
      window={26}
    />,
  );
  expect(
    screen.getByText("Arbitrary title levels by gathering, not crafting"),
  ).toBeTruthy();
  expect(
    screen.getByText("No catalog recipe within the next 26 points"),
  ).toBeTruthy();
  expect(screen.queryByRole("table")).toBeNull();
});
it("formats hire/Team steps with unknowns and sorts on copper", async () => {
  wrap(<Steps estimate={estimate} />);
  await userEvent.click(screen.getByText("Cost steps"));
  expect(screen.getAllByText("unknown").length).toBeGreaterThan(0);
  const values = () =>
    [...screen.getByRole("table").querySelectorAll("tbody tr")].map(
      (r) => r.textContent,
    );
  expect(values()[0]).toContain("1g");
  await userEvent.click(screen.getByRole("button", { name: /^Cost/ }));
  await userEvent.click(screen.getByRole("button", { name: /^Cost/ }));
  expect(values()[0]).toContain("2s");
});
it("shows tier feed savings, fees, levels, incomplete reasons and empty cost steps", () => {
  wrap(
    <HireDetail
      data={{
        ...detail,
        tiers: [
          ...detail.tiers,
          {
            ...detail.tiers[0],
            cap: 150,
            estimate: { ...estimate, steps: [] },
            feeds: { count: 0, top: [] },
          },
        ],
      }}
    />,
  );
  expect(screen.getByText("What it feeds: feeds nothing")).toBeTruthy();
  expect(screen.getByText("No cost steps available.")).toBeTruthy();
  expect(screen.getAllByText(/incomplete: training cost unknown/)).toHaveLength(
    2,
  );
  expect(screen.getByText("Rank 75 · character level 10")).toBeTruthy();
});
