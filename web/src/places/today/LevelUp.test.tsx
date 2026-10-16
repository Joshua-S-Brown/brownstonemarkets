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
    screen.getAllByText(/skill-up range unknown:/, { selector: "p" }),
  ).toHaveLength(2);
  expect(
    screen
      .getByRole("link", { name: "Kobold Tunneler (NPC 475)" })
      .getAttribute("href"),
  ).toBe("https://www.wowhead.com/classic/npc=475");
  expect(screen.getByText(/10 units\/hour/).textContent).toContain("no price");
  expect(screen.getByText(/Your own past sessions/)).toBeTruthy();
});
