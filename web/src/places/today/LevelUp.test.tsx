import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { InspectorContext } from "../../app/InspectorContext";
import { LevelUp } from "./LevelUp";
it("groups equal reaches once, preserves unknown costs/bands, farming rates and NPC links", () => {
  const recipe = {
    output_item_id: 1,
    name: "Cloth",
    profit_copper: null,
    board_reason: "missing prices",
    skillup_band: "skill-up range unknown: catalog has no colour bands",
    required_skill: 25,
    estimate: {
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
  fireEvent.click(screen.getByRole("button", { name: "Basilly" }));
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
it("shows three priced recipes per reach, expands the rest, and groups missing prices", async () => {
  const { cleanup } = await import("@testing-library/react");
  cleanup();
  const recipes = Array.from({ length: 6 }, (_, i) => ({
    output_item_id: 100 + i,
    name: `Recipe ${i}`,
    profit_copper: i < 4 ? 100 : null,
    board_reason: "missing prices",
    skillup_band: "needs 35 · you're 31 · orange 35, yellow 50",
    required_skill: 35,
    estimate: { complete: true, cost_copper: 405, reasons: [] },
  }));
  render(
    <InspectorContext.Provider value={vi.fn()}>
      <LevelUp
        session={{
          characters: [
            {
              character: ["Arille", "Beta", "Alliance"],
              options_text: [],
              professions: [
                {
                  profession: "Blacksmithing",
                  rank: 31,
                  max_rank: 75,
                  recipes,
                  milestones: [
                    { skill: 35, estimate: recipes[0].estimate, recipes },
                  ],
                  capped: false,
                  tier: null,
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
          ],
        }}
      />
    </InspectorContext.Provider>,
  );
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
