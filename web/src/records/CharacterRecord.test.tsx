import {
  render,
  screen,
  fireEvent,
  within,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { Inspector } from "../app/Inspector";
import { useInspector } from "../app/InspectorContext";
import * as Dialog from "@radix-ui/react-dialog";
import { todayKey } from "../places/today/state";
import { CharacterRecord } from "./CharacterRecord";
import type { RecordData } from "../places/team/types";
vi.mock("./CharacterHistory", () => ({
  CharacterHistory: () => <p>No readable level or rank history yet.</p>,
}));
afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});
function data(realm = "First"): RecordData {
  return {
    catalog_professions: {},
    free_slots: null,
    suggestions: [],
    suggestion_note: "professions unknown",
    character: ["Maker", realm, "Alliance"],
    card: {
      name: "Maker",
      realm,
      faction: "Alliance",
      machine: null,
      last_seen_relative: "unknown",
      last_seen_utc: "2026-10-17T10:00:00Z",
      level: null,
      gold_copper: null,
      stale: false,
      skills_status: "skills unknown",
      known_recipes: 3,
      recipes_at_least: true,
      professions: [
        {
          name: "Tailoring",
          rank: null,
          max_rank: null,
          known_count: null,
          recipe_source: "unknown",
          recipes_at: "2026-10-17T09:00:00Z",
          seen_at: null,
          possibly_incomplete: true,
          at_cap: false,
        },
      ],
      history: [],
    },
    progression: {
      unlisted: { fixture: 7 },
      professions: [
        {
          profession: "Tailoring",
          rank: 1,
          max_rank: 75,
          note: "",
          best: null,
          alternative: null,
          alternative_kind: null,
          gathering: false,
          next_step: "none",
          recipes: [
            {
              recipe_id: 2,
              catalog_id: "tailoring",
              name: "Linen shirt",
              output_item_id: 2,
              required_skill: 2,
              points_needed: 1,
              confidence: "Low",
              learn_from: "trainer",
              profit_copper: 40,
              estimate: {
                material_notes: ["Held 3 Linen Cloth from Maker’s bags · worth 30c if sold"],
                complete: true,
                cost_copper: 20,
                reasons: [],
                steps: [],
              },
              payback: { status: "absent", crafts: null },
            },
          ],
        },
      ],
    },
    holdings: {
      value_copper: 0,
      at_least: true,
      unpriced: 1,
      captures: [
        { kind: "bank", unknown: true, age_hours: null, partial: false },
        { kind: "bags", unknown: false, age_hours: 2, partial: true },
      ],
      items: [
        {
          item_id: 10,
          name: "Monkey robe",
          variant_state: "variant",
          variant_id: "v1:s1",
          units: 2,
          kind: "bags",
        },
      ],
    },
    evidence: {
      snapshot_ids: ["bags-1"],
      realm,
      source_id: "source",
      market_id: "market",
      scan_id: "scan",
    },
  };
}
function Links() {
  const inspect = useInspector();
  const url = useLocation();
  return (
    <>
      <button
        onClick={() => inspect({ character: ["Maker", "First", "Alliance"] })}
      >
        First
      </button>
      <button
        onClick={() => inspect({ character: ["Maker", "Second", "Alliance"] })}
      >
        Second
      </button>
      <output>{url.search}</output>
    </>
  );
}
function wrap(
  child: React.ReactNode,
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } }),
) {
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/app/team?source=source"]}>
        <Dialog.Root>{child}</Dialog.Root>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
it("requests distinct full identities, keeps characters out of URLs, and supports reopening", async () => {
  const calls: URL[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: URL) => {
      calls.push(url);
      return {
        ok: true,
        json: async () =>
          url.pathname === "/api/today/plan"
            ? { state: {}, stops: [] }
            : url.pathname.endsWith("/next")
              ? {
                  stops: [],
                  holdings: data().holdings,
                  gold: { categories: [] },
                }
              : data(url.searchParams.get("realm")!),
      };
    }),
  );
  wrap(
    <Inspector source="source">
      <Links />
    </Inspector>,
  );
  await userEvent.click(screen.getByText("First"));
  await screen.findByRole("heading", { name: "Maker" });
  expect(calls[0].searchParams.get("realm")).toBe("First");
  expect(screen.getByText("?source=source")).toBeTruthy();
  await userEvent.click(screen.getByText("Close ✕"));
  await userEvent.click(screen.getByText("Second"));
  await screen.findByRole("heading", { name: "Maker" });
  expect(
    calls
      .filter((c) => c.pathname === "/api/team/character")[1]
      .searchParams.get("realm"),
  ).toBe("Second");
  expect(
    calls
      .filter((c) => c.pathname === "/api/team/character")[1]
      .searchParams.get("name"),
  ).toBe("Maker");
  expect(
    calls
      .filter((c) => c.pathname === "/api/team/character")[1]
      .searchParams.get("faction"),
  ).toBe("Alliance");
  expect(screen.getByText("?source=source")).toBeTruthy();
});
it("renders unknown values, recipe provenance, partial captures, exact variants and history", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: URL) => ({
      ok: true,
      json: async () =>
        url.pathname === "/api/today/plan"
          ? { state: {}, stops: [] }
          : url.pathname.endsWith("/next")
            ? { stops: [], holdings: data().holdings, gold: { categories: [] } }
            : data(),
    })),
  );
  wrap(
    <CharacterRecord
      source="source"
      character={["Maker", "First", "Alliance"]}
    />,
  );
  await screen.findByRole("heading", { name: "Maker" });
  expect(screen.getByText(/Level unknown/).textContent).toContain(
    "17 Oct 10:00 UTC",
  );
  const facts = screen.getByLabelText("Character facts");
  expect(facts.textContent).toContain(
    "GoldunknownProfessions1Known recipesat least 3",
  );
  await userEvent.click(screen.getByRole("tab", { name: "Professions" }));
  await userEvent.hover(
    screen.getByRole("button", { name: "Recipe evidence" }),
  );
  expect(await screen.findByRole("tooltip")).toHaveProperty(
    "textContent",
    expect.stringContaining("possibly incomplete"),
  );
  await userEvent.click(screen.getByRole("tab", { name: "Path" }));
  const path = screen.getByRole("tabpanel");
  expect(within(path).queryByText("Unlisted")).toBeNull();
  expect(
    within(screen.getByRole("contentinfo")).getByText("Unlisted"),
  ).toBeTruthy();
  expect(
    within(path).getByRole("columnheader", { name: "Skill" }).closest("tr")
      ?.children,
  ).toHaveLength(4);
  await userEvent.hover(within(path).getByRole("button", { name: "ⓘ" }));
  expect(await screen.findByRole("tooltip")).toHaveProperty(
    "textContent",
    expect.stringContaining("1 points · Low confidence · trainer"),
  );
  fireEvent.mouseDown(screen.getByRole("tab", { name: "Holdings" }), {
    button: 0,
    ctrlKey: false,
  });
  fireEvent.click(screen.getByRole("tab", { name: "Holdings" }));
  expect(screen.getByText("Contents unknown")).toBeTruthy();
  expect(screen.getByText(/at least 2 units/)).toBeTruthy();
  // A lone identity carries no label.
  expect(screen.getByRole("listitem").textContent).not.toContain("variant");
  const item = screen.getByRole("button", { name: "Monkey robe" });
  const capture = screen.getByText("Capture evidence");
  expect(
    item.compareDocumentPosition(capture) & Node.DOCUMENT_POSITION_FOLLOWING,
  ).toBeTruthy();
  expect(within(facts).queryByText("Holdings")).toBeNull();
  expect(document.body.textContent).not.toMatch(/\d{4}-\d\d-\d\dT\d\d:/);
  expect(screen.getByRole("button", { name: "Monkey robe" })).toBeTruthy();
  fireEvent.mouseDown(screen.getByRole("tab", { name: "History" }), {
    button: 0,
    ctrlKey: false,
  });
  fireEvent.click(screen.getByRole("tab", { name: "History" }));
  await screen.findByText("No readable level or rank history yet.");
  expect(screen.getByText("bags-1")).toBeTruthy();
});

it("labels a holding only beside another identity, not another stack of the same one", async () => {
  const record = data();
  record.holdings.items.push({ ...record.holdings.items[0]!, kind: "bank" });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: URL) => ({
      ok: true,
      json: async () =>
        url.pathname === "/api/today/plan"
          ? { state: {}, stops: [] }
          : url.pathname.endsWith("/next")
            ? { stops: [], holdings: record.holdings, gold: { categories: [] } }
            : record,
    })),
  );
  wrap(
    <CharacterRecord
      source="source"
      character={["Maker", "First", "Alliance"]}
    />,
  );
  await screen.findByRole("heading", { name: "Maker" });
  await userEvent.click(screen.getByRole("tab", { name: "Holdings" }));
  const stacks = screen.getAllByRole("listitem");
  expect(stacks).toHaveLength(2);
  stacks.forEach((row) => expect(row.textContent).not.toContain("variant"));
});

it("opens Next with the shared Today query, original Route numbers and per-profession best", async () => {
  const record = data();
  record.free_slots = 1;
  record.holdings.items.push({
    item_id: 10,
    name: "Monkey robe",
    variant_state: "base",
    variant_id: null,
    units: 3,
    unit_copper: 5,
    value_copper: 15,
    action: "sell",
    kind: "bags",
  });
  record.suggestion_note = "";
  record.suggestions = ["blacksmithing", "leatherworking", "engineering"].map(
    (profession, i) => ({
      profession,
      holders: [
        { character: ["Arille", "First", "Alliance"], rank: 31, max_rank: 75 },
      ],
      best: { output_item_id: 10, output_name: "Helm", profit_copper: 26131 },
      best_now:
        i === 2
          ? null
          : {
              output_item_id: 11,
              output_name: "Mace",
              profit_copper: i === 1 ? -80 : 172,
            },
      estimate: {
        material_notes: [],
        complete: false,
        cost_copper: null,
        reasons: ["unknown starter"],
        steps: [],
      },
    }),
  );
  const g = record.progression.professions[0];
  g.best = {
    ...g.recipes[0],
    training_cost_copper: 100,
    payback: { status: "crafts", crafts: 3 },
  };
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  client.setQueryData(todayKey("source"), {
    state: { context: "shared", choices: [], refill: false },
    stops: [],
  });
  const fetcher = vi.fn(async (url: URL) => ({
    ok: true,
    json: async () =>
      url.pathname.endsWith("/next")
        ? {
            holdings: record.holdings,
            stops: [
              {
                number: 6,
                place: "auction house",
                lines: [{ index: 4, text: "Buy 12 Copper Bar", evidence: {} }],
              },
            ],
            gold: {
              in_copper: 100,
              out_copper: 30,
              net_copper: 70,
              categories: [],
            },
          }
        : record,
  }));
  vi.stubGlobal("fetch", fetcher);
  wrap(
    <CharacterRecord
      source="source"
      character={["Maker", "First", "Alliance"]}
    />,
    client,
  );
  expect(
    await screen.findByRole("link", { name: "Route step 6" }),
  ).toHaveProperty(
    "href",
    expect.stringContaining("/today?source=source&view=route"),
  );
  expect(
    screen.getByRole("tab", { name: "Next" }).getAttribute("aria-selected"),
  ).toBe("true");
  expect(screen.getByText("Buy 12 Copper Bar")).toBeTruthy();
  expect(
    screen.getByRole("heading", { name: "1 free profession slot" }),
  ).toBeTruthy();
  expect(
    screen
      .getAllByRole("heading", { name: /^Take up/ })
      .map((h) => h.textContent),
  ).toEqual([
    "Take up Blacksmithing",
    "Take up Leatherworking",
    "Take up Engineering",
  ]);
  expect(
    screen.getByText("Best now: nothing priced within 25 points"),
  ).toBeTruthy();
  expect(screen.getAllByText(/Best now:/)[1].textContent).toContain("-80c");
  expect(screen.getAllByText("Incomplete")).toHaveLength(3);
  await userEvent.click(screen.getAllByText("Estimate reasons")[0]);
  expect(screen.getAllByText("unknown starter")).toHaveLength(3);
  expect(
    screen.getAllByText("unknown starter")[0].closest("details")?.open,
  ).toBe(true);
  expect(screen.getAllByText(/has it/)).toHaveLength(3);
  expect(
    fetcher.mock.calls.some(([url]) => url.pathname.includes("/hire/")),
  ).toBe(false);

  expect(screen.getByText("needs skill 2 · trainer")).toBeTruthy();
  expect(screen.getByText(/Held 3 Linen Cloth/, { selector: "p" })).toBeTruthy();
  expect(screen.getByText("pays back training in 3 crafts")).toBeTruthy();
  expect(screen.getByText(/Came in/).textContent).toContain("Net: 70c");
  expect(
    fetcher.mock.calls.every(([url]) => url.pathname !== "/api/today/plan"),
  ).toBe(true);
  const next = fetcher.mock.calls.find(([url]) =>
    url.pathname.endsWith("/next"),
  );
  expect(next).toBeTruthy();
  await userEvent.click(screen.getByRole("tab", { name: "Holdings" }));
  const stacks = within(
    screen.getByRole("list", { name: "bags stacks" }),
  ).getAllByRole("listitem");
  expect(
    stacks.map((row) => [...row.children].map((cell) => cell.textContent)),
  ).toEqual([
    ["Monkey robe variant", "at least 2 units", "no price", "—", "keep"],
    ["Monkey robe ", "at least 3 units", "5c / unit", "15c total", "sell"],
  ]);
});

it("opens exact-skill profession headings, follows materials to items and goes Back across all three records", async () => {
  const character = data();
  character.catalog_professions = { "197": "tailoring" };
  character.progression.professions[0].skill_id = 197;
  character.card.professions[0].skill_id = 197;
  character.card.professions.push({
    ...character.card.professions[0],
    skill_id: 999,
  });
  const calls: URL[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: URL) => {
      calls.push(url);
      if (url.pathname === "/api/items/2589")
        return new Promise<never>(() => {});
      return {
        ok: true,
        json: async () =>
          url.pathname === "/api/team/profession/tailoring"
            ? {
                profession: "tailoring",
                holders: [
                  {
                    character: character.character,
                    rank: 32,
                    max_rank: 75,
                    known_count: 1,
                    note: "",
                  },
                ],
                rows: [
                  {
                    catalog_id: "forever-tailoring",
                    recipe_id: 1,
                    name: "Linen shirt",
                    output_item_id: 2,
                    required_skill: 1,
                    band: "1–24",
                    range_text: "skill-up range unknown",
                    learn_from: "trainer",
                    profit_copper: null,
                    board_reason: "No snapshot for this source and market.",
                    materials: [
                      { item_id: 2589, quantity: 2, name: "Linen Cloth" },
                    ],
                    statuses: [
                      {
                        craft_status: "Train now",
                        character_reason: "",
                        training_cost_copper: 100,
                      },
                    ],
                  },
                  {
                    catalog_id: "forever-tailoring",
                    recipe_id: 3,
                    name: "Linen belt",
                    output_item_id: 4,
                    required_skill: 1,
                    band: "1–24",
                    range_text: "",
                    learn_from: "trainer",
                    profit_copper: 47,
                    board_reason: "stale data",
                    materials: [],
                    statuses: [
                      {
                        craft_status: "Known",
                        character_reason: "",
                        training_cost_copper: null,
                      },
                    ],
                  },
                ],
                catalogs: [
                  {
                    catalog_id: "forever-tailoring",
                    catalog_version: "1",
                    coverage: "coverage unknown; regenerate the catalog",
                  },
                ],
                evidence: {
                  source_id: "source",
                  market_id: "market",
                  scan_id: null,
                  freshness: null,
                },
              }
            : url.pathname === "/api/today/plan"
              ? { state: {}, stops: [] }
              : url.pathname.endsWith("/next")
                ? {
                    stops: [],
                    holdings: character.holdings,
                    gold: { categories: [] },
                  }
                : character,
      };
    }),
  );
  wrap(
    <Inspector source="source">
      <Links />
    </Inspector>,
  );
  await userEvent.click(screen.getByText("First"));
  await screen.findByRole("heading", { name: "Maker" });
  await userEvent.click(screen.getByRole("button", { name: "Tailoring" }));
  await screen.findByRole("heading", { name: "Tailoring" });
  expect(screen.getByText(/32\/75 · 1 known catalog recipes/)).toBeTruthy();
  expect(screen.getByText(/No snapshot/)).toBeTruthy();
  expect(screen.getByText(/· stale data/)).toBeTruthy();
  expect(screen.getByText(/training/).textContent).toContain("1s");
  const recipes = screen.getByRole("table", { name: "Tailoring recipes" });
  expect(within(recipes).getAllByRole("columnheader")).toHaveLength(5); // 4 columns + 1 band.
  expect(
    within(recipes).getByRole("columnheader", { name: "Maker" }),
  ).toBeTruthy();
  expect(within(recipes).getAllByRole("row")).toHaveLength(4);
  expect(screen.getByText("?source=source")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Linen Cloth" })).toBeNull();
  await userEvent.click(
    screen.getByRole("button", { name: "Linen shirt details" }),
  );
  expect(screen.getByText(/learned from trainer/)).toBeTruthy();
  await userEvent.click(screen.getByRole("button", { name: "Linen Cloth" }));
  await waitFor(() =>
    expect(calls.some((u) => u.pathname === "/api/items/2589")).toBe(true),
  );
  expect(await screen.findByText("Loading saved item…")).toBeTruthy();
  expect(screen.getByText("?source=source&inspect=2589")).toBeTruthy();
  await userEvent.click(screen.getByRole("button", { name: "← Back" }));
  await screen.findByRole("heading", { name: "Tailoring" });
  await userEvent.click(screen.getByRole("button", { name: "← Back" }));
  await screen.findByRole("heading", { name: "Maker" });
  await userEvent.click(screen.getByRole("tab", { name: "Path" }));
  expect(screen.getByRole("button", { name: "Tailoring" })).toBeTruthy();
  await userEvent.click(screen.getByRole("tab", { name: "Professions" }));
  expect(screen.getAllByRole("button", { name: "Tailoring" })).toHaveLength(1);
  await userEvent.click(screen.getByRole("button", { name: "Tailoring" }));
  await screen.findByRole("heading", { name: "Tailoring" });
  expect(
    calls
      .filter((u) => u.pathname.includes("/profession/"))
      .every((u) => u.searchParams.get("source") === "source"),
  ).toBe(true);
});
