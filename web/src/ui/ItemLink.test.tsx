import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { ItemLink } from "./ItemLink";
import { InspectorContext } from "../app/InspectorContext";
it("uses plain text colour for unknown quality and opens its own record", async () => {
  const open = vi.fn();
  render(
    <InspectorContext.Provider value={open}>
      <ItemLink id={2589} name="Linen Cloth" />
    </InspectorContext.Provider>,
  );
  const link = screen.getByRole("button", { name: "Linen Cloth" });
  expect(link.style.color).toBe("");
  await userEvent.click(link);
  expect(open).toHaveBeenCalledWith({ item: 2589 });
});
it("uses only the captured quality colour", () => {
  render(<ItemLink id={1} name="Captured" quality={3} />);
  expect(screen.getByRole("button").style.color).toBe("var(--q-3)");
});
