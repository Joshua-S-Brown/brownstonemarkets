import { expect, it } from "vitest";
import { originLink } from "./Origin";
it("keeps validated Today tab/view and source, excludes invalid origins and characters", () => {
  const p = new URLSearchParams({
    origin_place: "Today",
    origin_tab: "Sell",
    origin_view: "This session",
  });
  expect(originLink(p, "one")?.url).toBe(
    "/?place=Today&source=one&tab=Sell&view=This+session",
  );
  p.set("origin_tab", "Unknown");
  expect(originLink(p, "one")).toBeNull();
  expect(
    originLink(
      new URLSearchParams({
        origin_place: "Market",
        origin_item: "2996",
        origin_name: "Bolt",
      }),
      "one",
    )?.url,
  ).toContain("inspect=2996");
  expect(
    originLink(
      new URLSearchParams({
        origin_place: "Market",
        origin_item: "oops",
        origin_name: "Bolt",
      }),
      "one",
    ),
  ).toBeNull();
});
