import { render, screen, fireEvent, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { Inspector } from "../app/Inspector";
import { useInspector } from "../app/InspectorContext";
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
function wrap(child: React.ReactNode) {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter initialEntries={["/app/team?source=source"]}>
        {child}
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
        json: async () => data(url.searchParams.get("realm")!),
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
  expect(calls[1].searchParams.get("realm")).toBe("Second");
  expect(calls[1].searchParams.get("name")).toBe("Maker");
  expect(calls[1].searchParams.get("faction")).toBe("Alliance");
  expect(screen.getByText("?source=source")).toBeTruthy();
});
it("renders unknown values, recipe provenance, partial captures, exact variants and history", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, json: async () => data() })),
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
  await userEvent.hover(
    screen.getByRole("button", { name: "Recipe evidence" }),
  );
  expect(await screen.findByRole("tooltip")).toHaveProperty(
    "textContent",
    expect.stringContaining("possibly incomplete"),
  );
  await userEvent.click(screen.getByRole("tab", { name: "Path" }));
  const path = screen.getByRole("tabpanel");
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
