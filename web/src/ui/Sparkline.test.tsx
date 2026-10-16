import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { Sparkline } from "./parts";
it("says there is not enough history instead of drawing NaN points", () => {
  render(<Sparkline values={[]} label="Price" />);
  expect(screen.getByText("Price: not enough history")).toBeTruthy();
  render(<Sparkline values={[3, 5]} label="Two scans" />);
  expect(
    screen.getByRole("img", { name: "Two scans" }).innerHTML,
  ).not.toContain("NaN");
});
it("never connects absent/null-price scans or turns gaps into zero", () => {
  const { container } = render(
    <Sparkline values={[10, null, 20, 30]} label="Gaps" />,
  );
  expect(container.querySelectorAll("line")).toHaveLength(1);
  expect(container.innerHTML).not.toContain("NaN");
});
