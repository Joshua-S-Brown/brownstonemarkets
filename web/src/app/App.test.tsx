import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";
afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});
it("requires explicit source choice, preserves it in place links and remembers the theme", async () => {
  const sockets: { url: URL; closed: boolean }[] = [];
  vi.stubGlobal(
    "WebSocket",
    class {
      entry: { url: URL; closed: boolean };
      constructor(url: URL) {
        this.entry = { url, closed: false };
        sockets.push(this.entry);
      }
      close() {
        this.entry.closed = true;
      }
    },
  );
  const user = userEvent.setup();
  const option = {
    source_id: "one",
    label: "Forever beta",
    game_version: "forever",
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: URL) => ({
      ok: true,
      json: async () => ({
        sources: [option, { ...option, source_id: "two" }],
        selected: url.searchParams.get("source") ? option : null,
        evidence: null,
        questions: {
          Today: "What should I do?",
          Market: "What is the market telling me?",
        },
        waiting: 3,
        waiting_error: null,
      }),
    })),
  );
  const rendered = render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  await screen.findByRole("heading", { name: "Choose a source" });
  await user.click(screen.getByRole("button", { name: "Choose source ▾" }));
  await user.click(
    screen.getAllByRole("button", { name: "forever · Forever beta" })[0],
  );
  await waitFor(() =>
    expect(
      within(screen.getByRole("navigation", { name: "Places" }))
        .getByRole("link", { name: /Today/ })
        .getAttribute("href"),
    ).toContain("source=one"),
  );
  await user.selectOptions(screen.getByLabelText("Theme"), "light");
  expect(localStorage.getItem("brownstone-theme")).toBe("light");
  expect(document.documentElement.dataset.theme).toBe("light");
  expect(sockets[0]?.url.searchParams.get("source")).toBe("one");
  rendered.unmount();
  expect(sockets.every((s) => s.closed)).toBe(true);
});
