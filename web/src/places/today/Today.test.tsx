import { render, screen, waitFor, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { reasonText } from "./Opportunities";
import { InspectorContext } from "../../app/InspectorContext";
import { Today } from "./Today";
import { OurMove } from "./OurMove";
import { type Plan, keepLocal, todayKey, readState, writeState } from "./state";
const craft = {
  catalog_id: "fixture",
  recipe_id: 30,
  batch_size: 2,
  output_item_id: 3,
  output_name: "Robe",
  made_by: "Basilly",
  profession: "tailoring",
  headline_profit_copper: 1234,
  headline_per_craft_copper: 617,
  profit_basis: "",
  confidence: "Low",
  confidence_reasons: ["thin listings"],
  feasible_size: 5,
};
function fixture(): Plan {
  return {
    state: {
      context: "one",
      queue_identity: "q",
      ticks: {},
      rows: [craft],
      choices: null,
      refill: true,
    },
    plan: {
      craft: [craft],
      sell: [{ output_item_id: 3 }],
      queue: {
        lines: [{}],
        mail_note: "Postage is unconfirmed.",
        expected_profit_copper: 1234,
        gold_needed_copper: 100,
      },
      freshness: { stale: false, upstream_known: true, age_hours: 2 },
      dropped_choices: [],
    },
    stops: [
      {
        stage: "craft",
        character: "Basilly",
        characters: [["Basilly", "Beta", "Alliance"]],
        place: "tailoring · rank 8",
        lines: [
          {
            index: 0,
            text: "Craft 2 Robe",
            evidence: { batch_size: 2 },
            warnings: "",
          },
        ],
      },
    ],
    reset_note: "",
    empty_reason: "",
    evidence: {},
    copy_text: "Craft 2 Robe\nGold needed: 1s",
    funds_copper: 5000,
    funds_label: "Our team",
    settings: {
      gold_copper: 10000,
      minimum_copper: 1000,
      max_crafts: 5,
      mode: "fixed",
      percent_basis_points: 100,
      post_duration_hours: 24,
      gold_override: false,
      include_unknown: false,
      character: null,
    },
    characters: [["Basilly", "Beta", "Alliance"]],
    notes: [],
    session: null,
  };
}
function URL() {
  return <output data-testid="url">{useLocation().search}</output>;
}
const inspect = vi.fn();
let data: Plan;
let requests: {
  url: string;
  body: { view?: string; state?: Plan["state"]; settings?: object };
  headers?: HeadersInit;
}[];
beforeEach(() => {
  inspect.mockClear();
  data = fixture();
  requests = [];
  sessionStorage.clear();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: URL, init: RequestInit) => {
      const body = JSON.parse(
        String(init?.body || "{}"),
      ) as (typeof requests)[number]["body"];
      requests.push({ url: String(input), body, headers: init?.headers });
      const result = String(input).includes("settings")
        ? body.settings
        : {
            ...data,
            state: body.state?.context ? body.state : data.state,
            session:
              body.view === "level-up"
                ? data.session || {
                    characters: [],
                    lever: null,
                    tier_explanation: "Captured tiers",
                  }
                : null,
          };
      return { ok: true, json: async () => result };
    }),
  );
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
function mount(
  view = "route",
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } }),
) {
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/app/today?source=one&view=" + view]}>
        <InspectorContext.Provider value={inspect}>
          <Today source="one" waiting={2} />
        </InspectorContext.Provider>
        <URL />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}
it("Route defaults, ticks survive refresh per source, copy matches Queue and URL chooses lazy Level up", async () => {
  const user = userEvent.setup();
  mount();
  await screen.findByText("Craft 2 Robe");
  await waitFor(() =>
    expect(requests.some((r) => r.body.view === "level-up")).toBe(true),
  );
  expect(screen.queryByLabelText("Biggest lever")).toBeNull();
  expect(requests[0].body.view).toBe("route");
  expect(screen.getByText("2 scans waiting")).toBeTruthy();
  await user.click(screen.getByRole("checkbox", { name: "Craft 2 Robe" }));
  expect(readState("one").ticks?.["0"]).toBe(true);
  expect(readState("other")).toEqual({});
  await user.click(screen.getByText("Copy as text"));
  expect(await navigator.clipboard.readText()).toBe(data.copy_text);
  cleanup();
  mount();
  await screen.findByText("Craft 2 Robe");
  expect(
    (screen.getByRole("checkbox", { name: "Craft 2 Robe" }) as HTMLInputElement)
      .checked,
  ).toBe(true);
  await user.click(screen.getByRole("tab", { name: "Level up" }));
  await screen.findByText(
    "No scoped Today characters imported. Open each profession window next login.",
  );
  expect(screen.getByTestId("url").textContent).toContain("view=level-up");
  expect(requests.some((r) => r.body.view === "level-up")).toBe(true);
});
it("Opportunities retain ranking, money, reasons and Hide Low leaves Route complete", async () => {
  const user = userEvent.setup();
  data.plan.freshness.stale = true;
  data.session = {
    lever: {
      character: ["Second", "Beta", "Alliance"],
      profession: "Tailoring",
      reach: 55,
      cost_copper: 100,
      profit_copper: 200,
      text: "Best next skill step",
    },
    characters: [
      {
        character: ["First", "Beta", "Alliance"],
        options_text: ["Level Cooking · unlocks Food"],
        next_steps: [{ kind: "level_profession" }],
      },
      {
        character: ["Second", "Beta", "Alliance"],
        options_text: ["Level Tailoring · unlocks Robe"],
        next_steps: [{ kind: "level_profession" }],
      },
    ],
  };
  mount("opportunities");
  const lever = await screen.findByLabelText("Biggest lever");
  expect(lever.textContent).toContain("Second");
  expect(lever.textContent).toContain("Best next skill step");
  expect(lever.textContent).not.toContain("First");
  await screen.findByRole("button", { name: "Robe" });
  expect(screen.getByRole("button", { name: "Low" })).toBeTruthy();
  expect(
    screen.getByRole("link", { name: "Open Data" }).getAttribute("href"),
  ).toBe("?source=one&view=opportunities&sheet=data");
  await user.click(screen.getByLabelText("Hide Low confidence"));
  expect(screen.queryByRole("button", { name: "Robe" })).toBeNull();
  await user.click(screen.getByRole("tab", { name: "Route" }));
  await screen.findByText("Craft 2 Robe");
  expect(readState("one").hide_low).toBe(true);
});
it("Our move is absent without a loaded ranked item, uses the existing query, and submits the same choices/refill", async () => {
  const user = userEvent.setup();
  const client = new QueryClient();
  const ui = (id: number) => (
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/app/today?view=level-up"]}>
        <OurMove source="one" id={id} />
      </MemoryRouter>
    </QueryClientProvider>
  );
  const view = render(ui(3));
  expect(screen.queryByText("Our move")).toBeNull();
  expect(requests).toHaveLength(0);
  client.setQueryData(todayKey("one"), data);
  await screen.findByText("Our move");
  expect(requests).toHaveLength(0);
  await user.click(screen.getByLabelText("Refill freed gold"));
  await waitFor(() => expect(requests).toHaveLength(1));
  expect(requests[0].body.state?.refill).toBe(false);
  expect(requests[0].body.view).toBe("level-up");
  expect(requests[0].body.state?.choices).toEqual([
    { catalog_id: "fixture", recipe_id: 30, batch_size: 2 },
  ]);
  const batch = screen.getByLabelText("Batch size");
  await user.clear(batch);
  await user.type(batch, "3");
  await user.tab();
  await waitFor(() => expect(requests).toHaveLength(2));
  expect(requests[1].body.state?.choices?.[0].batch_size).toBe(3);
  view.rerender(ui(999));
  expect(screen.queryByText("Our move")).toBeNull();
  expect(requests).toHaveLength(2);
});
it("Our move keeps an excluded craft, re-includes it at its remembered size and refuses invalid batches", async () => {
  const user = userEvent.setup();
  const client = new QueryClient();
  client.setQueryData(todayKey("one"), data);
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/app/today"]}>
        <OurMove source="one" id={3} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  const batch = await screen.findByLabelText("Batch size");
  await user.clear(batch);
  await user.type(batch, "9");
  await user.tab();
  expect((await screen.findByRole("alert")).textContent).toContain(
    "from 1 to 5",
  );
  expect(requests).toHaveLength(0);
  data = { ...data, plan: { ...data.plan, craft: [], sell: [] } };
  await user.click(screen.getByLabelText("Include craft"));
  await waitFor(() => expect(requests).toHaveLength(1));
  expect(requests[0].body.state?.choices?.[0].batch_size).toBeNull();
  await screen.findByText("Not in tonight’s plan.");
  await user.click(screen.getByLabelText("Include craft"));
  await waitFor(() => expect(requests).toHaveLength(2));
  expect(requests[1].body.state?.choices?.[0].batch_size).toBe(2);
});
it("settings are Save-only, Cancel discards draft and Save sends explicit money with the launch token", async () => {
  const meta = document.createElement("meta");
  meta.name = "brownstone-token";
  meta.content = "test-token";
  document.head.append(meta);
  const user = userEvent.setup();
  mount();
  await screen.findByText("Craft 2 Robe");
  await user.click(screen.getByRole("button", { name: "Today settings" }));
  await user.clear(screen.getByLabelText("Entered gold"));
  await user.type(screen.getByLabelText("Entered gold"), "15g");
  expect(requests.some((r) => r.url.includes("settings"))).toBe(false);
  await user.click(screen.getByText("Cancel"));
  await user.click(screen.getByRole("button", { name: "Today settings" }));
  expect(
    (screen.getByLabelText("Entered gold") as HTMLInputElement).value,
  ).toBe("1g");
  expect(screen.queryByLabelText("Percentage of gold available")).toBeNull();
  await user.selectOptions(screen.getByLabelText("Minimum mode"), "scaled");
  await user.clear(screen.getByLabelText("Percentage of gold available"));
  await user.type(screen.getByLabelText("Percentage of gold available"), "2.5");
  await user.click(screen.getByText("Save Today settings"));
  await waitFor(() =>
    expect(requests.some((r) => r.url.includes("settings"))).toBe(true),
  );
  const saved = requests.find((r) => r.url.includes("settings"))!;
  expect(saved.body.settings).toMatchObject({
    gold_text: "1g",
    minimum_text: "10s",
    percent_basis_points: 250,
  });
  expect(saved.headers).toMatchObject({ "X-Brownstone-Token": "test-token" });
  meta.remove();
});
it("unreadable storage starts a clean source and changed contexts come back from the server", () => {
  sessionStorage.setItem("brownstone-today-one", "broken");
  expect(readState("one")).toEqual({});
  writeState("one", { context: "fresh", ticks: {} });
  expect(readState("one")).toEqual({ context: "fresh", ticks: {} });
});
it("a response keeps ticks made in flight unless its Queue identity or context changed", () => {
  writeState("one", { ...data.state, ticks: { "0": true }, hide_low: true });
  expect(keepLocal("one", data).state).toMatchObject({
    ticks: { "0": true },
    hide_low: true,
  });
  const moved = { ...data, state: { ...data.state, queue_identity: "new" } };
  expect(keepLocal("one", moved).state.ticks).toEqual({});
  const reset = { ...data, state: { ...data.state, context: "two" } };
  expect(keepLocal("one", reset).state.hide_low).toBeUndefined();
});

it("uses the Team window for Level up", async () => {
  sessionStorage.setItem("brownstone-team-one", "40");
  mount();
  await screen.findByRole("tab", { name: "Level up" });
  expect(requests[0].body.state).toMatchObject({ window: 40 });
});

it("renders each purchase crafter as its own full-key character link", async () => {
  data.stops[0].characters = [
    ["Maker", "First", "Alliance"],
    ["Maker", "Second", "Horde"],
  ];
  mount();
  const first = (await screen.findAllByRole("button", { name: "Maker" }))[0]!;
  expect(first.parentElement!.textContent).toMatch(/Maker\s+·/);
  await userEvent.click(first);
  await userEvent.click(screen.getByTitle("Second · Horde"));
  expect(inspect.mock.calls.map((c) => c[0])).toEqual([
    { character: ["Maker", "First", "Alliance"] },
    { character: ["Maker", "Second", "Horde"] },
  ]);
});

it("renders short character names without the full identity in page text", async () => {
  mount();
  await screen.findByText("Craft 2 Robe");
  expect(document.body.textContent).not.toMatch(
    /(?:Maker|Basilly) · (?:Realm(?: [12])?|Beta) · Alliance/,
  );
});
it("compact lines link items and keep confidence reasons and original recipe text in evidence", async () => {
  data.stops[0].lines[0] = {
    index: 0,
    text: "Craft Robe · recipe 30 (fixture) · Low confidence (thin listings)",
    warnings: "contested",
    display: {
      item_id: 3,
      quality: 2,
      skillup_band: "orange at rank 8 · orange 1, yellow 10",
    },
    evidence: {
      stage: "craft",
      name: "Robe",
      batch_size: 2,
      recipe_id: 30,
      catalog_id: "fixture",
      confidence: "Low",
      confidence_reasons: ["thin listings"],
    },
  };
  mount();
  await screen.findByRole("heading", { name: "Route" });
  expect(
    screen.getAllByRole("button", { name: "Robe" })[0].getAttribute("style"),
  ).toContain("--q-2");
  expect(screen.getByText("thin listings").closest("details")?.open).toBe(
    false,
  );
  screen.getAllByRole("button", { name: "Low" })[0].focus();
  await waitFor(() =>
    expect(screen.getByRole("tooltip").textContent).toContain("thin listings"),
  );
  await userEvent.click(screen.getByRole("button", { name: "Line evidence" }));
  expect(await screen.findByText(data.stops[0].lines[0].text)).toBeTruthy();
  expect(screen.getAllByText("contested").length).toBeGreaterThan(0);
});
it("Route renders while the lever request is unresolved; then Biggest lever scrolls to and focuses its card", async () => {
  let release: (value: unknown) => void = () => {};
  const original = fetch;
  vi.stubGlobal("fetch", (input: URL, init: RequestInit) => {
    const body = JSON.parse(String(init?.body || "{}"));
    if (body.view === "level-up")
      return new Promise((resolve) => {
        release = resolve;
      });
    return original(input, init);
  });
  mount();
  await screen.findByText("Craft 2 Robe");
  expect(screen.queryByLabelText("Biggest lever")).toBeNull();
  const group = {
    profession: "Blacksmithing",
    rank: 31,
    max_rank: 75,
    best: {
      catalog_id: "fixture",
      recipe_id: 1,
      output_item_id: 2,
      name: "Wristguards",
      points_needed: 19,
      required_skill: 50,
      profit_copper: 9250,
      confidence: "Low",
      estimate: { complete: true, cost_copper: 405, steps: [], reasons: [] },
    },
    recipes: [],
    milestones: [],
  };
  const scroll = vi.fn();
  vi.spyOn(HTMLElement.prototype, "scrollIntoView").mockImplementation(scroll);
  release({
    ok: true,
    json: async () => ({
      ...data,
      session: {
        lever: {
          character: ["Arille", "Beta", "Alliance"],
          profession: "Blacksmithing",
          reach: 50,
          cost_copper: 405,
          profit_copper: 9250,
          text: "Best skill step 31 → 50",
        },
        characters: [
          {
            character: ["Arille", "Beta", "Alliance"],
            options_text: [
              "Craft boots",
              "Level Blacksmithing 31 → 50 for 4s 5c · unlocks Wristguards at 92s 50c per craft",
            ],
            next_steps: [
              { kind: "craft" },
              { kind: "level_profession", group },
            ],
            professions: [group],
            crafts: [],
            farming: {
              rows: [],
              spots: [],
              recorded_seconds: 0,
              excluded_stretches: 0,
            },
          },
        ],
      },
    }),
  });
  expect((await screen.findByLabelText("Biggest lever")).textContent).toContain(
    "31 → 50",
  );
  expect(screen.getByLabelText("Biggest lever").textContent).toContain(
    "Arille",
  );
  expect(screen.getByLabelText("Biggest lever").textContent).toContain(
    "Best skill step",
  );
  expect(screen.getByText("Craft 2 Robe")).toBeTruthy();
  await userEvent.click(screen.getByRole("button", { name: "Open Level up" }));
  const card = await screen.findByRole("region", {
    name: "Arille Blacksmithing",
  });
  await waitFor(() => expect(document.activeElement).toBe(card));
  expect(scroll).toHaveBeenCalledWith({ block: "start" });
  expect(screen.getByTestId("url").textContent).toContain("view=level-up");
  vi.restoreAllMocks();
});
it("unplanned opportunities explain eligibility and reset notes can be dismissed", async () => {
  data.reset_note = "Queue ticks reset";
  data.plan.unplanned = [
    {
      catalog_id: "fixture",
      recipe_id: 40,
      output_item_id: 4,
      output_name: "Bag",
      profession: "Tailoring",
      required_skill: 75,
      tonight_reason: "rank below required skill",
      profit_copper: 200,
    },
  ];
  mount();
  expect(await screen.findByText(/needs Tailoring 75/)).toBeTruthy();
  await userEvent.click(
    screen.getByRole("button", { name: "Dismiss reset notice" }),
  );
  expect(screen.queryByText("Queue ticks reset")).toBeNull();
});

it("post quantities retain held outputs beside crafted units", async () => {
  data.stops[0].lines[0] = {
    index: 0,
    text: "Post 2 crafted + 3 held",
    warnings: "",
    display: { item_id: 3, quality: 2 },
    evidence: {
      stage: "post",
      name: "Robe",
      quantity: 2,
      unit_copper: 100,
      profit_copper: 50,
      deposit_copper: 100,
      held_outputs: [{ units: 3, character: "Basilly", kind: "bank" }],
    },
  };
  mount();
  expect(await screen.findByText("+ 3 held (Basilly, bank)")).toBeTruthy();
});
it("capitalises catalog profession names in unplanned reasons", () => {
  expect(
    reasonText({
      tonight_reason: "rank below required skill",
      profession: "blacksmithing",
      required_skill: 175,
    } as Parameters<typeof reasonText>[0]),
  ).toBe("needs Blacksmithing 175");
});

it.each([
  ["craft", " · uses 6 Copper Bar you hold"],
  ["mail", ", for White Linen Robe and Linen Bag (step 9)"],
  [
    "take",
    " out of the bank, for White Linen Robe (step 9), then mail them to Basilly",
  ],
])(
  "shows the shared held-material wording on compact %s lines",
  async (stage, note) => {
    data.stops[0].lines[0] = {
      index: 0,
      text: `Action${note}`,
      warnings: "",
      display: { item_id: 3, action_note: note },
      evidence: { stage, name: "Robe", units: 8, to: "Basilly" },
    };
    mount();
    expect(
      await screen.findByText((text) => text.endsWith(note.trim())),
    ).toBeTruthy();
    expect(
      screen.getByRole("checkbox", { name: `Action${note}` }),
    ).toBeTruthy();
  },
);

it("shows vendor fallback and vendor value only for priced opportunities", async () => {
  data.plan.craft[0] = { ...craft, vendor_profit_copper: -30 };
  data.plan.sell[0].vendor_instead = true;
  data.plan.unplanned = [
    {
      catalog_id: "other",
      recipe_id: 31,
      output_item_id: 4,
      output_name: "Boots",
      profession: "tailoring",
      tonight_reason: "not selected tonight",
      profit_copper: 50,
    },
  ];
  data.stops[0].place = "vendor";
  data.stops[0].lines[0] = {
    index: 0,
    text: "Sell: Robe · vendor it instead · 1s 90c each",
    evidence: {
      stage: "post",
      name: "Robe",
      quantity: 2,
      unit_copper: 190,
      profit_copper: 350,
      vendor_instead: true,
    },
    display: { item_id: 3 },
    warnings: "",
  };
  mount();
  expect(await screen.findByText(/Vendor it instead 2/)).toBeTruthy();
  expect(screen.queryByText("Post")).toBeNull();
  expect(
    screen.getByText("Deposits excluded: refunded on an auction sale"),
  ).toBeTruthy();
  expect(screen.getAllByText(/Vendor value/)).toHaveLength(1);
  expect(
    screen.getByRole("button", { name: "Boots" }),
  ).toBeTruthy();
  expect(screen.getByText("At planned auction or vendor value")).toBeTruthy();
});
