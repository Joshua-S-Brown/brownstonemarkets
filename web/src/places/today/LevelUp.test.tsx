import {
  fireEvent,
  render,
  screen,
  within,
  waitFor,
} from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { InspectorContext } from "../../app/InspectorContext";
import { LevelUp } from "./LevelUp";
it("groups equal reaches once, preserves unknown costs/bands, farming rates and NPC links", async () => {
  const recipe = {
    output_item_id: 1,
    name: "Cloth",
    profit_copper: null,
    board_reason: "missing prices",
    skillup_band: "skill-up range unknown: catalog has no colour bands",
    required_skill: 25,
    estimate: {
      material_notes: [
        "Held 3 Linen Cloth from Basilly’s bags · worth 30c if sold",
        "Or farm ≈ 0.5 h at Forest (Basilly’s own rate) · your own past sessions, not a promise",
      ],
      complete: false,
      cost_copper: null,
      reasons: ["training cost unknown"],
    },
  };
  const recipe2 = { ...recipe, output_item_id: 2, name: "Robe" };
  const group = {
    profession: "Tailoring",
    rank: 8,
    max_rank: 75,
    recipes: [recipe, recipe2],
    milestones: [
      { skill: 25, estimate: recipe.estimate, recipes: [recipe, recipe2] },
    ],
    tier: null,
    capped: false,
  };
  const inspect = vi.fn();
  render(
    <InspectorContext.Provider value={inspect}>
      <LevelUp
        session={{
          characters: [
            {
              character: ["Basilly", "Beta", "Alliance"],
              options_text: ["Train Journeyman at a trainer"],
              professions: [group],
              crafts: [],
              level: 6,
              farming: {
                rows: [
                  {
                    item_id: 3,
                    item_name: "Linen",
                    units_per_hour: 10,
                    value_per_hour_copper: null,
                    zone: "Forest",
                    source_kind: "mob",
                    seconds: 300,
                  },
                ],
                spots: [
                  {
                    npc_id: 475,
                    mob: "Kobold Tunneler (NPC 475)",
                    zone: "Forest",
                    position: "around 47, 72",
                    value_per_hour_copper: 1000,
                    seconds: 300,
                    stretches: 1,
                    coin_share: "Coin unavailable",
                    no_price_items: 1,
                    no_price_units: 2,
                  },
                ],
                recorded_seconds: 300,
                excluded_stretches: 1,
              },
            },
          ],
        }}
      />
    </InspectorContext.Provider>,
  );
  expect(
    screen.getByRole("list", { name: "No levelling step" }).textContent,
  ).toContain("Basilly · Tailoring · Train Journeyman at a trainer");
  expect(screen.queryAllByRole("region")).toHaveLength(0);
  fireEvent.click(
    within(screen.getByRole("list", { name: "No levelling step" })).getByRole(
      "button",
      { name: "Basilly" },
    ),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Is it paying off? · Basilly" }),
  );
  expect(inspect).toHaveBeenCalledWith({
    character: ["Basilly", "Beta", "Alliance"],
    tab: "Earnings",
  });
  fireEvent.click(screen.getByText("All tiers and recipes · Tailoring"));
  await waitFor(() =>
    expect(screen.getByText("2 with missing prices")).toBeTruthy(),
  );
  fireEvent.click(screen.getByText("2 with missing prices"));
  expect(
    screen.getByText(/Held 3 Linen Cloth/, { selector: "p" }),
  ).toBeTruthy();
  expect(screen.getByText(/Or farm ≈ 0.5 h/, { selector: "p" })).toBeTruthy();
  expect(inspect).toHaveBeenCalledWith({
    character: ["Basilly", "Beta", "Alliance"],
  });
  expect(
    screen.getAllByRole("heading", {
      name: "Reach 25 · cost unknown · training cost unknown",
    }),
  ).toHaveLength(1);
  expect(
    screen.getAllByRole("button", { name: /skill-up range unknown:/ }),
  ).toHaveLength(2);
  expect(
    screen
      .getByRole("link", { name: "Kobold Tunneler (NPC 475)" })
      .getAttribute("href"),
  ).toBe("https://www.wowhead.com/classic/npc=475");
  expect(screen.getByText(/10 units\/hour/).textContent).toContain("no price");
  expect(screen.getByText(/Your own past sessions/)).toBeTruthy();
});
it("orders levelling cards, marks ranks, preserves unknown costs and no-step reasons, and discloses all tiers", async () => {
  const { cleanup } = await import("@testing-library/react");
  cleanup();
  const recipes = Array.from({ length: 6 }, (_, i) => ({
    output_item_id: 100 + i,
    name: `Recipe ${i}`,
    profit_copper: i < 4 ? 100 : null,
    board_reason: "missing prices",
    skillup_band: "needs 35 · you're 31 · orange 35, yellow 50",
    recipe_id: 100 + i,
    catalog_id: "fixture",
    points_needed: 4,
    confidence: "Low",
    needs_pattern: true,
    skillup_colors: [25, 50, 60, 75],
    required_skill: 35,
    estimate: {
      complete: false,
      cost_copper: 0,
      reasons: ["training cost unknown"],
      steps: [{ recipe: "Stone" }, { recipe: "Stone" }, { recipe: "Bar" }],
    },
  }));
  render(
    <InspectorContext.Provider value={vi.fn()}>
      <LevelUp
        session={{
          characters: [
            {
              character: ["Arille", "Beta", "Alliance"],
              options_text: [
                "Craft boots",
                "Level Blacksmithing",
                "Level Cooking",
              ],
              next_steps: [
                { kind: "craft" },
                {
                  kind: "level_profession",
                  group: { profession: "Blacksmithing" },
                },
                { kind: "level_profession", group: { profession: "Cooking" } },
              ],
              professions: [
                {
                  profession: "Blacksmithing",
                  rank: 31,
                  max_rank: 75,
                  best: recipes[0],
                  recipes,
                  milestones: [
                    { skill: 35, estimate: recipes[0].estimate, recipes },
                  ],
                  capped: false,
                  tier: null,
                },
                {
                  profession: "Cooking",
                  rank: 2,
                  max_rank: 75,
                  best: {
                    ...recipes[1],
                    profit_copper: -11,
                    estimate: {
                      ...recipes[1].estimate,
                      complete: true,
                      cost_copper: 1104,
                    },
                  },
                  recipes: [recipes[1]],
                  milestones: [],
                  capped: false,
                },
                {
                  profession: "Mining",
                  rank: 48,
                  best: {
                    ...recipes[0],
                    estimate: { complete: false, reasons: ["missing colour"] },
                  },
                  milestones: [],
                },
              ],
              crafts: [],
              level: 10,
              farming: {
                rows: [],
                spots: [],
                recorded_seconds: 0,
                excluded_stretches: 0,
              },
            },
            {
              character: ["Basilly", "Beta", "Alliance"],
              options_text: ["Level Tailoring"],
              next_steps: [
                {
                  kind: "level_profession",
                  group: { profession: "Tailoring" },
                },
              ],
              professions: [
                {
                  profession: "Tailoring",
                  rank: 32,
                  max_rank: 75,
                  best: { ...recipes[2], profit_copper: null },
                  recipes: [],
                  milestones: [],
                },
              ],
              crafts: [],
              farming: {
                rows: [],
                spots: [],
                recorded_seconds: 0,
                excluded_stretches: 0,
              },
            },
            {
              character: ["Cicelyna", "Beta", "Alliance"],
              options_text: ["No professions seen yet"],
              next_steps: [{ kind: "evidence" }],
              professions: [],
              crafts: [],
              farming: {
                rows: [],
                spots: [],
                recorded_seconds: 0,
                excluded_stretches: 0,
              },
            },
          ],
        }}
      />
    </InspectorContext.Provider>,
  );
  const cards = screen.getAllByRole("region");
  expect(cards.map((c) => c.getAttribute("aria-label"))).toEqual([
    "Arille Blacksmithing",
    "Arille Cooking",
    "Basilly Tailoring",
  ]);
  expect(
    within(cards[1]).getByText("Earns per craft").nextElementSibling!
      .textContent,
  ).toBe("-11c");
  expect(
    within(cards[1]).getByText("Materials to reach").nextElementSibling!
      .textContent,
  ).toBe("11s 4c");
  expect(
    within(cards[2]).getByText("Earns per craft").nextElementSibling!
      .textContent,
  ).toBe("unknown");
  const card = within(cards[0]);
  expect(card.getByText("Levels on Stone, Bar")).toBeTruthy();
  expect(
    card.getByText("Materials to reach").nextElementSibling!.textContent,
  ).toBe("unknown · training cost unknown");
  expect(card.getByText("Low confidence · needs a pattern")).toBeTruthy();
  expect(
    screen.getByRole("list", { name: "No levelling step" }).textContent,
  ).toContain("Mining · missing colour");
  expect(
    screen.getByRole("list", { name: "No levelling step" }).textContent,
  ).toContain("Cicelyna · no profession seen · No professions seen yet");
  const bands = screen.getAllByRole("meter");
  expect(
    bands.map((b) => [
      b.getAttribute("aria-valuemin"),
      b.getAttribute("aria-valuenow"),
      b.getAttribute("aria-valuemax"),
    ]),
  ).toEqual([
    ["25", "31", "90"],
    ["2", "2", "90"],
  ]);
  expect(bands[0].querySelector("i")?.style.left).toBe(`${(100 * 6) / 65}%`);
  expect(bands[1].querySelector("i")?.style.left).toBe("0%");
  expect(card.getByText("All tiers and recipes").closest("details")?.open).toBe(
    false,
  );

  fireEvent.click(card.getByText("All tiers and recipes"));
  await waitFor(() =>
    expect(card.getByRole("heading", { name: /Reach 35/ })).toBeTruthy(),
  );
  expect(
    screen.getByText("Craft boots").closest("details")?.textContent,
  ).toContain("Other session options");
  expect(screen.getByText("1 more").closest("details")?.open).toBe(false);
  expect(
    screen.getByText("2 with missing prices").closest("details")?.open,
  ).toBe(false);
  expect(
    screen
      .getAllByRole("button", { name: /needs 35 · you're 31/ })
      .filter(
        (button) =>
          !button.closest("details") || button.closest("details")?.open,
      ),
  ).toHaveLength(3);
  fireEvent.click(screen.getByText("1 more"));
  expect(
    screen
      .getAllByRole("button", { name: /needs 35 · you're 31/ })
      .filter(
        (button) =>
          !button.closest("details") || button.closest("details")?.open,
      ),
  ).toHaveLength(4);
});
