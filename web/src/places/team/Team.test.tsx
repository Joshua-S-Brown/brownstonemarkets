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
import { SkillBar, skillFraction, MemberCard } from "./Roster";
import { Coverage, coverageRows } from "./Coverage";
import { HiringTables } from "./HiringTables";
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
const row = {
  profession: "tailoring",
  holders: [],
  best: null,
  best_now: null,
  estimate,
};
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
      free_slots: null,
      suggestions: [],
      suggestion_note: "professions unknown",
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
        known_recipes: 3,
        recipes_at_least: false,
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
      progression: { professions: [group], best_step: group },
    })),
    planned: [],
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
  await screen.findAllByRole("button", { name: "Maker" });
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
  await userEvent.click(screen.getAllByTitle("Realm 1 · Alliance")[0]);
  await userEvent.click(screen.getAllByTitle("Realm 2 · Alliance")[0]);
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
  expect(((await screen.findByRole("slider")) as HTMLInputElement).value).toBe(
    "30",
  );
  sessionStorage.setItem("brownstone-team-one", "101");
  expect(readWindow("one")).toBe(25);
  sessionStorage.setItem("brownstone-team-one", "{");
  expect(readWindow("one")).toBe(25);
});
it("loads hire detail only on first opening and retains it when reopened", async () => {
  wrap(<Hire row={row} source="one" />);
  expect(requests).toHaveLength(0);
  const disclosure = screen.getByText("Tailoring").closest("details")!;
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
  const view = wrap(
    <Path
      groups={[
        {
          ...group,
          recipes: [
            ...group.recipes,
            {
              ...recipe,
              name: "Smelt Copper",
              profit_copper: null,
              estimate: {
                ...estimate,
                reasons: ["Rank 48: Smelt Copper’s skill-up colour is unknown"],
              },
            },
          ],
        },
      ]}
      window={25}
    />,
  );
  const hidden = screen.getByText("1 more without a price").closest("details")!;
  expect(hidden.open).toBe(false);
  fireEvent.click(screen.getByText("1 more without a price"));
  expect(hidden.open).toBe(true);
  expect(
    screen.getAllByText(/Smelt Copper’s skill-up colour is unknown/).length,
  ).toBeGreaterThan(0);
  expect(screen.getByText("Or learn now")).toBeTruthy();
  expect(
    screen.getByText("reliable while you look for the pattern"),
  ).toBeTruthy();
  expect(
    screen.getByRole("columnheader", { name: "Skill" }).closest("tr")?.children,
  ).toHaveLength(4);
  expect(screen.queryByRole("columnheader", { name: /Learn from/ })).toBeNull();
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

it("renders short character names without the full identity in page text", async () => {
  wrap(<Team source="one" />);
  await screen.findAllByRole("button", { name: "Maker" });
  expect(document.body.textContent).not.toMatch(
    /(?:Maker|Basilly) · (?:Realm(?: [12])?|Beta) · Alliance/,
  );
});

it("uses rank/tier maths and leaves unknown maxima without a bar", () => {
  expect(skillFraction(31, 75)).toBe(31 / 75);
  expect(skillFraction(48, 75)).toBe(48 / 75);
  expect(skillFraction(90, 75)).toBe(1);
  expect(skillFraction(2, null)).toBeNull();
  expect(skillFraction(null, 75)).toBeNull();
  expect(skillFraction(2, 0)).toBeNull();
  const view = wrap(<SkillBar name="Blacksmithing" rank={31} maximum={75} />);
  const bar = screen.getByRole("progressbar", { name: "Blacksmithing" });
  expect(bar.getAttribute("aria-valuenow")).toBe("31");
  expect(bar.getAttribute("aria-valuemax")).toBe("75");
  expect((bar.firstChild as HTMLElement).style.width).toBe(
    `${(31 / 75) * 100}%`,
  );
  expect(screen.getByTitle("Next tier: 75")).toBeTruthy();
  view.rerender(<SkillBar name="Unknown" rank={31} maximum={null} />);
  expect(screen.queryByRole("progressbar")).toBeNull();
});
it("builds matrix cells with full character identity and gathering coverage", async () => {
  const data = fixture();
  data.hires[0].holders = [
    { character: data.roster[1].character, rank: 32, max_rank: 75 },
  ];
  data.roster[0].card.professions[0] = {
    ...data.roster[0].card.professions[0],
    name: "Fishing",
    rank: 3,
    max_rank: 75,
  };
  data.no_catalog.push("herbalism");
  wrap(<Coverage data={data} />);
  const rows = screen.getAllByRole("row");
  expect(rows[1].textContent).toContain("Tailoring·32");
  expect(rows[2].textContent).toContain("Fishing3·");
  expect(coverageRows(data)[1].holders[0].character).toEqual(
    data.roster[0].character,
  );
  expect(screen.getByText("Not covered")).toBeTruthy();
  await userEvent.hover(screen.getByRole("button", { name: "Fishing" }));
  await screen.findByRole("tooltip", {
    name: "No catalog: gathering income and supply are not modelled",
  });
});
it("keeps a best recipe action and replaces only missing recipe actions with a suggestion or honest gap", () => {
  const member = fixture().roster[0];
  member.progression.professions = [
    { ...group, best: { ...recipe, profit_copper: 1 } },
    {
      ...group,
      profession: "Tailoring",
      best: { ...recipe, name: "Best choice", profit_copper: 200 },
    },
  ];
  member.progression.best_step = member.progression.professions[1];
  const view = wrap(<MemberCard member={member} />);
  expect(screen.getAllByText(/Next step/)).toHaveLength(1);
  expect(screen.getByRole("button", { name: "Best choice" })).toBeTruthy();
  expect(view.container.textContent).toContain("2s");
  expect(
    screen.getByRole("button", { name: "All next steps and evidence" }),
  ).toBeTruthy();
  member.suggestions = [
    {
      ...row,
      profession: "blacksmithing",
      best: { output_item_id: 10, output_name: "Helm", profit_copper: 26131 },
      best_now: { output_item_id: 11, output_name: "Mace", profit_copper: 172 },
    },
  ];
  view.rerender(<MemberCard member={member} />);
  expect(screen.queryByText(/Take up/)).toBeNull();
  member.progression.best_step = { ...group, best: null };
  member.card.professions = [];
  view.rerender(<MemberCard member={member} />);
  expect(screen.getByText(/Take up Blacksmithing/).textContent).toBe(
    "Take up Blacksmithing: 1s 72c per craft now, 2g 61s 31c at 300",
  );
  member.card.professions = fixture().roster[0].card.professions;
  member.suggestions[0].best_now = null;
  view.rerender(<MemberCard member={member} />);
  expect(screen.getByText(/Take up Blacksmithing/).textContent).toContain(
    "nothing priced within the selected window",
  );
  member.suggestions = [];
  member.suggestion_note = "no profession has a priced recipe at 300";
  view.rerender(<MemberCard member={member} />);
  expect(screen.getByText(member.suggestion_note)).toBeTruthy();
  member.suggestion_note = "professions unknown";
  view.rerender(<MemberCard member={member} />);
  expect(screen.getByText("professions unknown")).toBeTruthy();
});
it("renders hire and holder table rows with complete/incomplete pills and reasons", async () => {
  const data = fixture();
  data.hires[0] = {
    ...row,
    best: { output_item_id: 10, output_name: "Craft", profit_copper: 200 },
    estimate: { ...estimate, complete: true, cost_copper: 300 },
  };
  data.comparisons = [
    {
      character: data.roster[0].character,
      professions: [{ profession: "cooking", best: { ...recipe, estimate } }],
    },
  ];
  wrap(<HiringTables data={data} source="one" window={25} />);
  expect(screen.getAllByRole("table")).toHaveLength(2);
  expect(screen.getByText("Complete")).toBeTruthy();
  expect(screen.getByText("Incomplete")).toBeTruthy();
  await userEvent.hover(screen.getByRole("button", { name: "Incomplete" }));
  await screen.findByRole("tooltip", { name: "training cost unknown" });
  expect(screen.getByText("Best per craft at 300")).toBeTruthy();
  expect(screen.getByText("Best per craft in reach")).toBeTruthy();
});

it("appends planned characters with roles, professions and cap summaries without opening a record", async () => {
  const data = fixture();
  data.planned = [
    {
      name: "Future",
      faction: "alliance",
      role: "priest",
      professions: [
        {
          profession: "tailoring",
          tiers: [
            {
              cap: 75,
              estimate: { ...estimate, complete: true, cost_copper: 123 },
              best: {
                output_name: "Robe",
                output_item_id: 1,
                profit_copper: 456,
              },
            },
            { cap: 150, estimate, best: null },
          ],
        },
      ],
    },
    { faction: "alliance", role: "warrior", professions: [] },
  ];
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, json: async () => data })),
  );
  wrap(<Team source="one" />);
  await screen.findByText("Future");
  const cards = screen.getAllByRole("article");
  expect(cards).toHaveLength(4);
  expect(cards[2].textContent).toContain("Future");
  expect(cards[2].textContent).toContain("priest");
  expect(cards[2].textContent).toContain("Tailoring");
  expect(cards[2].textContent).toContain("Cost to 75: 1s 23c");
  expect(cards[2].textContent).toContain("best profit per craft: 4s 56c");
  expect(cards[2].textContent).toContain("Cost to 150: unknown");
  expect(cards[2].textContent).toContain("best profit per craft: unknown");
  expect(cards[3].textContent).toContain("Unnamed character");
  expect(screen.getAllByText(/Planned, not created/)).toHaveLength(2);
  await userEvent.click(screen.getByText("Future"));
  expect(open).not.toHaveBeenCalled();
});

it("opens profession records from coverage and both hiring tables", async () => {
  const data = fixture();
  data.comparisons = [
    {
      character: ["Maker", "Realm 1", "Alliance"],
      professions: [{ profession: "tailoring", best: null }],
    },
  ];
  wrap(
    <>
      <Coverage data={data} />
      <HiringTables data={data} source="one" window={25} />
    </>,
  );
  const links = screen.getAllByRole("button", { name: "Tailoring" });
  expect(links).toHaveLength(3);
  for (const link of links) await userEvent.click(link);
  expect(open.mock.calls.map((c) => c[0])).toEqual(
    Array(3).fill({ profession: "tailoring" }),
  );
  expect(requests).toHaveLength(0);
});
