import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import vectors from "../../../tests/fixtures/money_vectors.json";
import { Money } from "./Money";
describe("Money parity", () => {
  for (const row of vectors)
    it(String(row.copper), () => {
      const { container } = render(<Money copper={row.copper} />);
      expect(container.textContent).toBe(row.text);
    });
});
it("renders zero muted without coin colour classes", () => {
  const { container } = render(<Money copper={0} />);
  expect(container.firstElementChild?.className).toContain("muted");
  expect(container.querySelector('[class*="coin-"]')).toBeNull();
  expect(container.textContent).toBe("0c");
});
