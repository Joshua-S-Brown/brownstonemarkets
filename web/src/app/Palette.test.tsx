import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it, vi, afterEach } from "vitest";
import userEvent from "@testing-library/user-event";
import { Palette, placeURL } from "./Palette";
import { InspectorContext } from "./InspectorContext";
afterEach(() => vi.unstubAllGlobals());
it("filters places and records, navigates with keys, and closes with Escape", async () => {
  const open = vi.fn(),
    user = userEvent.setup();
  const fetcher = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => [
      { kind: "item", name: "Linen Cloth", item_id: 2589, quality: null },
      {
        kind: "character",
        name: "Maker · Realm · Alliance",
        item_id: null,
        quality: null,
      },
    ],
  });
  vi.stubGlobal("fetch", fetcher);
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <InspectorContext.Provider value={open}>
        <Palette source="forever" />
      </InspectorContext.Provider>
    </QueryClientProvider>,
  );
  await user.keyboard("{Meta>}k{/Meta}");
  await user.type(screen.getByRole("combobox"), "linen");
  await screen.findByText("Linen Cloth");
  expect(screen.queryByText("Today")).toBeNull();
  await user.keyboard("{ArrowDown}{Enter}");
  expect(open).toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: /Search items/ }));
  await user.keyboard("{Escape}");
  await waitFor(() => expect(screen.queryByRole("combobox")).toBeNull());
  expect(String(fetcher.mock.calls.at(-1)?.[0])).toContain("source=forever");
});

it("passes exact character keys from search hits and opens the Team web place", async () => {
  const open = vi.fn();
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue({
        ok: true,
        json: async () => [
          {
            kind: "character",
            name: "Maker · Other realm · Horde",
            character: ["Maker", "Other realm", "Horde"],
          },
        ],
      }),
  );
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <InspectorContext.Provider value={open}>
        <Palette source="one" />
      </InspectorContext.Provider>
    </QueryClientProvider>,
  );
  await userEvent.click(screen.getByRole("button", { name: /Search items/ }));
  await userEvent.type(screen.getByRole("combobox"), "Maker");
  await userEvent.click(await screen.findByText("Maker · Other realm · Horde"));
  expect(open).toHaveBeenCalledWith({
    character: ["Maker", "Other realm", "Horde"],
  });
  expect(placeURL("Team", "one")).toBe("/app/team?source=one");
});
