import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { Data } from "./Data";
import { App } from "../../app/App";
import { placeURL } from "../../app/Palette";
const selection = {
  new: true,
  default: ["one", "two"],
  selected: ["one", "two"],
  choices: ["one", "two"],
  can_import: true,
  has_records: false,
  problems: [],
  lines: ["2 new scans"],
  sections: [],
  notes: [],
  file_status: [],
  clear: [],
};
const reviewed = {
  review_id: "id",
  review: selection,
  messages: [],
  hits: [],
  success: false,
};
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
function setup() {
  const calls: { url: URL; body: Record<string, unknown> | null }[] = [];
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  vi.stubGlobal(
    "WebSocket",
    class {
      close() {}
    },
  );
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: URL, options?: RequestInit) => {
      const body = options?.body ? JSON.parse(String(options.body)) : null;
      calls.push({ url, body });
      let result: unknown = {
        provider: "addon",
        chips: ["0 scans imported", "Drop folder"],
        details: { source_id: url.searchParams.get("source") },
      };
      if (url.pathname.endsWith("/review")) result = reviewed;
      if (url.pathname.endsWith("/selection"))
        result = {
          ...selection,
          selected: body?.selected,
          selection_differs: true,
          problems: ["Selection differs from the default"],
        };
      if (url.pathname.endsWith("/import"))
        result = {
          review_id: null,
          review: null,
          messages: [["success", "Imported."]],
          hits: ["Linen hit"],
          success: true,
        };
      if (url.pathname.endsWith("/imported")) result = [];
      if (url.pathname.endsWith("/sources"))
        result = {
          sources: [
            { source_id: "one", label: "One", game_version: "forever" },
            { source_id: "two", label: "Two", game_version: "forever" },
          ],
          selected: {
            source_id: url.searchParams.get("source") || "one",
            label: "One",
          },
          questions: {},
          evidence: null,
          waiting: 2,
        };
      return { ok: true, json: async () => result };
    }),
  );
  return { client, calls, invalidate };
}
it("reviews only on click, selects subset, imports with exact review and invalidates every source query", async () => {
  const user = userEvent.setup();
  const { client, calls, invalidate } = setup();
  render(
    <QueryClientProvider client={client}>
      <Data source="one" />
    </QueryClientProvider>,
  );
  await screen.findByText("0 scans imported");
  expect(calls.some((c) => c.url.pathname.endsWith("/review"))).toBe(false);
  expect(calls.some((c) => c.url.pathname.endsWith("/imported"))).toBe(false);
  await user.click(screen.getByText("ⓘ Import details"));
  expect(screen.getByText("source id", { exact: false })).toBeTruthy();
  await user.click(screen.getByRole("button", { name: "Check for new scans" }));
  await screen.findByText("New evidence waiting");
  await user.click(screen.getByText("Details", { exact: true }));
  await user.click(screen.getByLabelText("two"));
  expect(screen.getByText("Selection differs from the default")).toBeTruthy();
  await user.click(screen.getByRole("button", { name: "Import" }));
  await screen.findByText("Imported.");
  expect(calls.find((c) => c.url.pathname.endsWith("/import"))?.body).toEqual({
    review_id: "id",
    selected: ["one"],
  });
  expect(invalidate).toHaveBeenCalled();
  expect(screen.getByText("Linen hit")).toBeTruthy();
  await user.click(screen.getByText("What's imported"));
  await waitFor(() =>
    expect(calls.some((c) => c.url.pathname.endsWith("/imported"))).toBe(true),
  );
});
it("opens from sheet=data, removes it on Close, and source switching discards client and server review", async () => {
  const user = userEvent.setup();
  const { client, calls } = setup();
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/app/ledger?source=one&sheet=data"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  await screen.findByRole("button", { name: "Check for new scans" });
  await user.click(screen.getByRole("button", { name: "Check for new scans" }));
  await screen.findByText("New evidence waiting");
  await user.click(screen.getByRole("button", { name: "Close ✕" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(
    calls.some(
      (c) => c.url.pathname.endsWith("/discard") && c.body?.review_id === "id",
    ),
  ).toBe(true);
  await user.click(screen.getByRole("button", { name: "Data 2" }));
  await screen.findByRole("button", { name: "Check for new scans" });
  expect(screen.queryByText("New evidence waiting")).toBeNull();
  await user.click(screen.getByRole("button", { name: "Close ✕" }));
  await user.click(screen.getByRole("button", { name: "One ▾" }));
  await user.click(screen.getByRole("button", { name: "forever · Two" }));
  await waitFor(() =>
    expect(calls.some((c) => c.url.searchParams.get("source") === "two")).toBe(
      true,
    ),
  );
  expect(placeURL("Data", "two")).toBe("/app/today?source=two&sheet=data");
  expect(placeURL("Ledger", "two")).toBe("/app/ledger?source=two");
});

it("discards an open review when a different source mounts the sheet", async () => {
  const user = userEvent.setup();
  const { client, calls } = setup();
  const view = (source: string) => (
    <QueryClientProvider client={client}>
      <Data key={source} source={source} />
    </QueryClientProvider>
  );
  const rendered = render(view("one"));
  await screen.findByRole("button", { name: "Check for new scans" });
  await user.click(screen.getByRole("button", { name: "Check for new scans" }));
  await screen.findByText("New evidence waiting");
  rendered.rerender(view("two"));
  await screen.findByRole("button", { name: "Check for new scans" });
  expect(screen.queryByText("New evidence waiting")).toBeNull();
  expect(
    calls.some(
      (c) =>
        c.url.pathname.endsWith("/discard") &&
        c.url.searchParams.get("source") === "one" &&
        c.body?.review_id === "id",
    ),
  ).toBe(true);
});
