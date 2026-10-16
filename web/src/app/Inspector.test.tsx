import { render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { Inspector } from "./Inspector";
import { ItemLink } from "../ui/ItemLink";
vi.mock("../records/ItemRecord", () => ({
  ItemRecord: ({ id }: { id: number }) => (
    <>
      <p>Record {id}</p>
      <ItemLink id={2996} name="Next bolt" />
    </>
  ),
}));
function URL() {
  return <output data-testid="url">{useLocation().search}</output>;
}
it("opens URL records on refresh, retains a back stack and clears URL on close", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={["/?source=one&inspect=2589"]}>
      <Inspector source="one">
        <ItemLink id={2996} name="Bolt" />
        <URL />
      </Inspector>
    </MemoryRouter>,
  );
  expect(screen.getByText("Record 2589")).toBeTruthy();
  await user.click(screen.getByText("Next bolt"));
  expect(screen.getByText("Record 2996")).toBeTruthy();
  expect(screen.getByTestId("url").textContent).toContain("inspect=2996");
  await user.click(screen.getByText("← Back"));
  expect(screen.getByText("Record 2589")).toBeTruthy();
  await user.click(screen.getByText("Close ✕"));
  expect(screen.getByTestId("url").textContent).toBe("?source=one");
});
