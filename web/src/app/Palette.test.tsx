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
        name: "Maker",
        character: ["Maker", "Realm", "Alliance"],
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
    vi.fn().mockResolvedValue({
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
  await userEvent.click(await screen.findByText("Maker"));
  expect(open).toHaveBeenCalledWith({
    character: ["Maker", "Other realm", "Horde"],
  });
  expect(open).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole("combobox")).toBeNull();
  expect(placeURL("Team", "one")).toBe("/app/team?source=one");
});

it("groups matching items and characters, hides empty groups and keeps variant keys in tooltips", async () => {
  const key = "v1:e41:g0,0,0,0:s0:b";
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [
        {
          kind: "item",
          name: "Linen Cloth",
          item_id: 2589,
          quality: 1,
          role: "Material",
          variant_state: "base",
        },
        {
          kind: "item",
          name: "Linen Bag",
          item_id: 4238,
          quality: 2,
          role: "Craft",
          variant_state: "base",
        },
        {
          kind: "item",
          name: "Barbaric Linen Vest",
          item_id: 2578,
          quality: 2,
          role: "Craft",
          variant_state: "variant",
          variant_id: key,
        },
      ],
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient()}>
      <Palette source="one" />
    </QueryClientProvider>,
  );
  await userEvent.click(screen.getByRole("button", { name: /Search items/ }));
  await userEvent.type(screen.getByRole("combobox"), "linen");
  await screen.findByText("Linen Cloth");
  expect(screen.getByText("Items")).toBeTruthy();
  expect(screen.queryByText("Go to")).toBeNull();
  expect(screen.queryByText("Characters")).toBeNull();
  expect(screen.getByText(/Material · 2589/)).toBeTruthy();
  expect(screen.getByText(/Craft · 4238/)).toBeTruthy();
  expect(screen.getByText("Linen Cloth").style.color).toBe("var(--q-1)");
  expect(screen.queryByText("base")).toBeNull();
  expect(document.body.textContent).not.toContain(key);
  expect(screen.getByTitle(key).textContent).toContain("variant");
});
it("shows only the ID for an item outside the catalogs, with its identity beside the name", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [
        {
          kind: "item",
          name: "Hearthstone",
          item_id: 6948,
          quality: 1,
          role: null,
          variant_state: "unresolved",
        },
      ],
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient()}>
      <Palette source="one" />
    </QueryClientProvider>,
  );
  await userEvent.click(screen.getByRole("button", { name: /Search items/ }));
  await userEvent.type(screen.getByRole("combobox"), "hearth");
  const name = await screen.findByText("Hearthstone");
  expect(screen.getByText("6948").textContent).toBe("6948");
  expect(name.parentElement!.textContent).toContain("unresolved");
});
