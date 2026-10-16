import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { Evidence, evidenceLabel } from "./Evidence";
it("labels every field, shows copper as money and keeps missing values unknown", () => {
  render(
    <Evidence
      data={{
        typical_copper: 12345,
        price_copper: null,
        stale: false,
        catalogs: ["tailoring", "enchanting"],
        rows: [],
        scan: { scan_id: "20261016T113727Z-eb77d0", units: 5538 },
        pairs: [{ gap: 3600, key: [2996, null, "base"] }],
        item_id: 2996,
        min_buyout: 7,
        holdings_warning: null,
      }}
    />,
  );
  expect(screen.getByText("Typical")).toBeTruthy();
  expect(screen.getByText("1g")).toBeTruthy();
  expect(screen.getByText("unknown")).toBeTruthy();
  expect(screen.getByText("2996")).toBeTruthy();
  expect(screen.getByText("7c")).toBeTruthy();
  expect(
    screen.getByRole("cell", { name: "2996, unknown, base" }),
  ).toBeTruthy();
  expect(screen.getByText("no")).toBeTruthy();
  expect(screen.getByText("tailoring, enchanting")).toBeTruthy();
  expect(screen.getAllByText("none")).toHaveLength(2);
  expect(screen.getByText("20261016T113727Z-eb77d0")).toBeTruthy();
  expect(screen.getByText("5,538")).toBeTruthy();
  expect(screen.getByRole("columnheader", { name: "Gap" })).toBeTruthy();
  expect(screen.getByRole("cell", { name: "3,600" })).toBeTruthy();
  expect(evidenceLabel("no_buyout_units")).toBe("No buyout units");
});
