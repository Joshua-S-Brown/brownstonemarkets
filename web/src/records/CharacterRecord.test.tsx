import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { Inspector } from "../app/Inspector";
import { useInspector } from "../app/InspectorContext";
import { CharacterRecord } from "./CharacterRecord";
import type { RecordData } from "../places/team/types";
vi.mock("./CharacterHistory", () => ({
  CharacterHistory: () => <p>No readable level or rank history yet.</p>,
}));
afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});
function data(realm = "First"): RecordData {
  return {
    character: ["Maker", realm, "Alliance"],
    card: {
      name: "Maker",
      realm,
      faction: "Alliance",
      machine: null,
      last_seen_relative: "unknown",
      last_seen_utc: "unknown",
      level: null,
      gold_copper: null,
      stale: false,
      skills_status: "skills unknown",
      professions: [
        {
          name: "Tailoring",
          rank: null,
          max_rank: null,
          known_count: null,
          recipe_source: "unknown",
          recipes_at: "unknown",
          seen_at: null,
          possibly_incomplete: true,
          at_cap: false,
        },
      ],
      history: [],
    },
    progression: { professions: [] },
    holdings: {
      captures: [
        { kind: "bank", unknown: true, age_hours: null, partial: false },
        { kind: "bags", unknown: false, age_hours: 2, partial: true },
      ],
      items: [
        {
          item_id: 10,
          name: "Monkey robe",
          variant_state: "variant",
          variant_id: "v1:s1",
          units: 2,
          kind: "bags",
        },
      ],
    },
    evidence: {
      snapshot_ids: ["bags-1"],
      realm,
      source_id: "source",
      market_id: "market",
      scan_id: "scan",
    },
  };
}
function Links() {
  const inspect = useInspector();
  const url = useLocation();
  return (
    <>
      <button
        onClick={() => inspect({ character: ["Maker", "First", "Alliance"] })}
      >
        First
      </button>
      <button
        onClick={() => inspect({ character: ["Maker", "Second", "Alliance"] })}
      >
        Second
      </button>
      <output>{url.search}</output>
    </>
  );
}
function wrap(child: React.ReactNode) {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter initialEntries={["/app/team?source=source"]}>
        {child}
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
it("requests distinct full identities, keeps characters out of URLs, and supports reopening", async () => {
  const calls: URL[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: URL) => {
      calls.push(url);
      return {
        ok: true,
        json: async () => data(url.searchParams.get("realm")!),
      };
    }),
  );
  wrap(
    <Inspector source="source">
      <Links />
    </Inspector>,
  );
  await userEvent.click(screen.getByText("First"));
  await screen.findByRole("heading", { name: "Maker" });
  expect(calls[0].searchParams.get("realm")).toBe("First");
  expect(screen.getByText("?source=source")).toBeTruthy();
  await userEvent.click(screen.getByText("Close ✕"));
  await userEvent.click(screen.getByText("Second"));
  await screen.findByRole("heading", { name: "Maker" });
  expect(calls[1].searchParams.get("realm")).toBe("Second");
  expect(calls[1].searchParams.get("name")).toBe("Maker");
  expect(calls[1].searchParams.get("faction")).toBe("Alliance");
  expect(screen.getByText("?source=source")).toBeTruthy();
});
it("renders unknown values, recipe provenance, partial captures, exact variants and history", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, json: async () => data() })),
  );
  wrap(
    <CharacterRecord
      source="source"
      character={["Maker", "First", "Alliance"]}
    />,
  );
  await screen.findByRole("heading", { name: "Maker" });
  expect(screen.getByText(/Level unknown/).textContent).toContain(
    "Gold unknown",
  );
  expect(
    screen.getByRole("heading", { name: "Tailoring · unknown / unknown" }),
  ).toBeTruthy();
  expect(screen.getByText(/Known recipes: unknown/)).toBeTruthy();
  expect(screen.getByText("possibly incomplete")).toBeTruthy();
  fireEvent.mouseDown(screen.getByRole("tab", { name: "Holdings" }), {
    button: 0,
    ctrlKey: false,
  });
  fireEvent.click(screen.getByRole("tab", { name: "Holdings" }));
  await waitFor(() => expect(screen.getByText("bank · unknown")).toBeTruthy());
  expect(screen.getByText("bags · 2.0 hours old · partial")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Monkey robe" })).toBeTruthy();
  fireEvent.mouseDown(screen.getByRole("tab", { name: "History" }), {
    button: 0,
    ctrlKey: false,
  });
  fireEvent.click(screen.getByRole("tab", { name: "History" }));
  await screen.findByText("No readable level or rank history yet.");
  expect(screen.getByText("bags-1")).toBeTruthy();
});
