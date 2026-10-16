import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { Sparkline } from "./parts";
it("says there is not enough history instead of drawing NaN points", () => {
  render(<Sparkline values={[]} label="Price" />);
  expect(screen.getByText("Price: not enough history")).toBeTruthy();
  render(<Sparkline values={[3, 5]} label="Two scans" />);
  expect(screen.getByRole("img", { name: "Two scans" }).innerHTML).not.toContain("NaN");
});
