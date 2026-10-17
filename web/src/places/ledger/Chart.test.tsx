import { expect, it } from "vitest";
import { flowRows } from "./Chart";
it("puts out below zero and in above without changing the response", () => {
  const rows = [{ day: "2026-10-17", in_copper: 6592, out_copper: 4324 }];
  expect(flowRows(rows)).toEqual([
    { day: "2026-10-17", in_copper: 6592, out_copper: -4324 },
  ]);
  expect(rows[0].out_copper).toBe(4324);
});
