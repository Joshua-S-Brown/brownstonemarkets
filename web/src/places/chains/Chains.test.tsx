import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { Chains, Graph, type Route } from "./Chains";
import { addToTonight, readState, writeState, type Plan } from "../today/state";
import { placeURL } from "../../app/Palette";
const output = {
  makeable: true,
  team_reason: "Basilly: Known",
  catalog_id: "tailoring",
  recipe_id: 3755,
  item_id: 4238,
  name: "Linen Bag",
  profession: "tailoring",
  profit_copper: 34,
};
function route(forced = false, batch = 1): Route {
  return {
    ...output,
    batch,
    max_crafts: 5,
    reason: "",
    can_add: true,
    nodes: [
      {
        output: false,
        sale_price_copper: null,
        listings: 2,
        item_id: 2996,
        name: "Bolt of Linen Cloth",
        units: 3,
        column: 1,
        method: forced ? "buy" : "craft",
        unit_cost_copper: forced ? 50 : 42,
        forced,
        options: [
          { method: "buy", unit_cost_copper: 50 },
          { method: "craft", unit_cost_copper: 42 },
        ],
        maker: "Basilly, Tailoring",
        characters: [],
        route_note: "",
        held: null,
        at_least: false,
      },
    ],
    edges: [],
    leaves: [],
    waterfall: [
      {
        label: "Profit",
        amount_copper: forced ? 10 : 34,
        start_copper: 0,
        end_copper: forced ? 10 : 34,
      },
    ],
    spend_copper: forced ? 180 : 156,
    profit_copper: forced ? 10 : 34,
    evidence: { basis: "Cautious" },
    source_evidence: { source_id: "beta", market_id: "market" },
  };
}
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});
it("refetches forced toggles and reset, applies server batch bounds, and uses the narrow semantic list", async () => {
  const urls: URL[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: URL) => {
      urls.push(url);
      return {
        ok: true,
        json: async () =>
          url.pathname.endsWith("/route")
            ? route(
                url.searchParams.has("force"),
                Number(url.searchParams.get("batch")),
              )
            : {
                ranked: [output, { ...output, recipe_id: 2393, name: "Robe" }],
                hits: [output],
              },
      };
    }),
  );
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter
        initialEntries={[
          "/app/chains?source=beta&catalog=tailoring&recipe=3755",
        ]}
      >
        <Chains source="beta" />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  const user = userEvent.setup();
  const group = await screen.findByRole("group", {
    name: "Bolt of Linen Cloth route",
  });
  await user.click(within(group).getByRole("button", { name: /^Buy/ }));
  await screen.findByText("forced");
  expect(urls.at(-1)!.searchParams.get("force")).toBe("2996:buy");
  await user.click(screen.getByRole("button", { name: "Reset to cheapest" }));
  await waitFor(() => expect(screen.queryByText("forced")).toBeNull());
  const slider = screen.getByRole("slider", { name: "Crafts" });
  expect(slider.getAttribute("min")).toBe("1");
  expect(slider.getAttribute("max")).toBe("5");
  fireEvent.change(slider, { target: { value: "5" } });
  await waitFor(() => expect(urls.at(-1)!.searchParams.get("batch")).toBe("5"));
  expect(urls.at(-1)!.searchParams.has("force")).toBe(false);
  expect(
    await screen.findByRole("list", { name: "Route from output to materials" }),
  ).toBeTruthy();
  await user.click(screen.getByRole("button", { name: /^Buy/ }));
  await screen.findByText("forced");
  await user.click(screen.getByRole("button", { name: "Robe · tailoring" }));
  await waitFor(() =>
    expect(urls.at(-1)!.searchParams.get("recipe_id")).toBe("2393"),
  );
  expect(urls.at(-1)!.searchParams.get("batch")).toBe("1");
  expect(urls.at(-1)!.searchParams.has("force")).toBe(false);
  expect(placeURL("Supply chains", "beta")).toBe("/app/chains?source=beta");
});
it("preserves graph toggles in the list", () => {
  const force = vi.fn();
  render(<Graph route={route()} force={force} />);
  fireEvent.click(screen.getByRole("button", { name: /^Buy/ }));
  expect(force).toHaveBeenCalledWith(2996, "buy");
});
it.each([false, true])(
  "adds or replaces Today choices, persists returned state and invalidates Today (replace=%s)",
  async (replace) => {
    const choice = { catalog_id: "tailoring", recipe_id: 3755, batch_size: 5 };
    const other = { catalog_id: "alchemy", recipe_id: 1, batch_size: 2 };
    writeState("beta", { context: "same", ticks: { one: true } });
    const requests: { state: Plan["state"] }[] = [];
    const client = new QueryClient();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: URL, options: RequestInit) => {
        const body = JSON.parse(options.body as string);
        requests.push(body);
        return {
          ok: true,
          json: async () => ({
            state: {
              ...body.state,
              choices:
                requests.length === 1
                  ? [other, ...(replace ? [{ ...choice, batch_size: 1 }] : [])]
                  : body.state.choices,
            },
            plan: { dropped_choices: [] },
          }),
        };
      }),
    );
    expect(await addToTonight("beta", choice, client)).toEqual({
      batch_size: 5,
      reason: undefined,
    });
    expect(requests[0].state.ticks).toEqual({ one: true });
    expect(requests[1].state.choices).toEqual([other, choice]);
    expect(readState("beta").choices).toEqual([other, choice]);
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["beta", "today"] });
    expect(JSON.stringify(requests)).not.toContain("forced");
  },
);
it("shows Today's dropped choice reason and an Open Today link", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: URL, options?: RequestInit) => ({
      ok: true,
      json: async () =>
        url.pathname.endsWith("today/plan")
          ? {
              state: JSON.parse(options!.body as string).state,
              plan: {
                dropped_choices: [
                  {
                    catalog_id: "tailoring",
                    recipe_id: 3755,
                    reason: "Not enough gold",
                  },
                ],
              },
            }
          : url.pathname.endsWith("/route")
            ? route()
            : { ranked: [output], hits: [output] },
    })),
  );
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter
        initialEntries={["/app/chains?catalog=tailoring&recipe=3755"]}
      >
        <Chains source="beta" />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  await userEvent.click(
    await screen.findByRole("button", { name: "Add to tonight" }),
  );
  expect(await screen.findByText(/Not enough gold/)).toBeTruthy();
  expect(
    screen.getByRole("link", { name: "Open Today" }).getAttribute("href"),
  ).toBe("/app/today?source=beta");
});

it("disables Add to tonight for an intermediate and shows its reason without sale or profit", async () => {
  const intermediate = {
    ...route(),
    can_add: false,
    reason: "Intermediate: no Action Board profit row",
    waterfall: [],
    profit_copper: null,
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: URL) => ({
      ok: true,
      json: async () =>
        url.pathname.endsWith("/route")
          ? intermediate
          : { ranked: [], hits: [output] },
    })),
  );
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter
        initialEntries={["/app/chains?catalog=tailoring&recipe=3755"]}
      >
        <Chains source="beta" />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  const button = await screen.findByRole("button", { name: "Add to tonight" });
  expect((button as HTMLButtonElement).disabled).toBe(true);
  expect(
    screen.getByText("Intermediate: no Action Board profit row"),
  ).toBeTruthy();
  expect(screen.queryByText("Sale")).toBeNull();
});
it("opens the top ranked craft and only lists capped search hits while searching", async () => {
  const urls: URL[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: URL) => {
      urls.push(url);
      return {
        ok: true,
        json: async () =>
          url.pathname.endsWith("/route")
            ? route(false, 1)
            : url.searchParams.get("q")
              ? { ranked: [output], hits: [output], hit_count: 120 }
              : { ranked: [output], hits: [], hit_count: 0 },
      };
    }),
  );
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter initialEntries={["/app/chains?source=beta"]}>
        <Chains source="beta" />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  await waitFor(() =>
    expect(
      urls.some((u) => u.pathname.endsWith("/route")) &&
        urls
          .find((u) => u.pathname.endsWith("/route"))!
          .searchParams.get("recipe_id"),
    ).toBe(String(output.recipe_id)),
  );
  expect(screen.queryByLabelText("Search results")).toBeNull();
  await userEvent
    .setup()
    .type(screen.getByLabelText(/Find an output/), "linen");
  expect(
    await screen.findByText("Showing 1 of 120; narrow the search."),
  ).toBeTruthy();
});
it("words held units without implying zero is a partial count", () => {
  const base = route();
  const node = base.nodes[0]!;
  const show = (held: number | null, at_least: boolean) => {
    cleanup();
    render(
      <Graph
        route={{ ...base, nodes: [{ ...node, held, at_least }] }}
        force={vi.fn()}
      />,
    );
  };
  show(null, false);
  expect(screen.getByText("Held: unknown")).toBeTruthy();
  show(0, false);
  expect(screen.getByText("None held")).toBeTruthy();
  show(0, true);
  expect(screen.getByText("None seen in captured bags and banks")).toBeTruthy();
  show(11, true);
  expect(screen.getByText("Held: at least 11")).toBeTruthy();
});

it.each([true, false])(
  "opens the projection's first chip with makeable=%s",
  async (makeable) => {
    const urls: URL[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: URL) => {
        urls.push(url);
        return {
          ok: true,
          json: async () =>
            url.pathname.endsWith("/route")
              ? route()
              : { ranked: [{ ...output, makeable }], hits: [], hit_count: 0 },
        };
      }),
    );
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <Chains source="beta" />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() =>
      expect(
        urls.some(
          (u) =>
            u.pathname.endsWith("/route") &&
            u.searchParams.get("recipe_id") === "3755",
        ),
      ).toBe(true),
    );
    expect(Boolean(screen.queryByText(/No ranked craft is makeable/))).toBe(
      !makeable,
    );
  },
);

it("draws curved solid chosen edges and dashed unchosen branches", () => {
  const r = route();
  r.nodes = [
    r.nodes[0]!,
    { ...r.nodes[0]!, item_id: 2589, name: "Linen Cloth", column: 2, units: 0 },
    {
      ...r.nodes[0]!,
      item_id: 4238,
      name: "Linen Bag",
      column: 0,
      output: true,
      sale_price_copper: 300,
    },
  ];
  r.edges = [
    { parent: 4238, child: 2996, quantity: 3, chosen: true },
    { parent: 2996, child: 2589, quantity: 2, chosen: false },
  ];
  const { container } = render(<Graph route={r} force={vi.fn()} />);
  const paths = container.querySelectorAll("path");
  expect(paths.length).toBe(2);
  expect(paths[0]!.getAttribute("d")).toContain("C");
  expect(paths[0]!.getAttribute("stroke-dasharray")).toBeNull();
  expect(paths[1]!.getAttribute("stroke-dasharray")).toBe("3 5");
  expect(screen.getByText("Sells at")).toBeTruthy();
  expect(screen.getByText("Output")).toBeTruthy();
  // An unchosen-branch node offers no route toggle: forcing it cannot change cost.
  expect(screen.getByText("Not on the chosen route")).toBeTruthy();
  expect(screen.queryByRole("group", { name: "Linen Cloth route" })).toBeNull();
});

it("scales an intermediate waterfall to its largest cost, not one copper", async () => {
  const { Waterfall } = await import("./Chains");
  const r = route();
  r.waterfall = [
    {
      label: "Linen Cloth",
      quantity: 2,
      unit_cost_copper: 50,
      amount_copper: -100,
      start_copper: 0,
      end_copper: -100,
    },
    {
      label: "Coarse Thread",
      quantity: 1,
      unit_cost_copper: 25,
      amount_copper: -25,
      start_copper: -100,
      end_copper: -125,
    },
  ];
  const { container } = render(<Waterfall route={r} />);
  const widths = [
    ...container.querySelectorAll<HTMLElement>("[data-negative] [style]"),
  ].map((b) => b.style.width);
  expect(widths).toEqual(["100%", "25%"]);
});

it("keeps labelled signed rows, quantity evidence and a negative total in one waterfall", async () => {
  const { Waterfall } = await import("./Chains");
  const r = route();
  r.waterfall = [
    { label: "Sale", amount_copper: 100, start_copper: 0, end_copper: 100 },
    {
      label: "Bauxite",
      quantity: 2,
      unit_cost_copper: 3900,
      amount_copper: -7800,
      start_copper: 100,
      end_copper: -7700,
    },
    {
      label: "Profit",
      amount_copper: -7700,
      start_copper: 0,
      end_copper: -7700,
    },
  ];
  const { container } = render(<Waterfall route={r} />);
  expect(screen.getByText("Bauxite")).toBeTruthy();
  expect(screen.getByText(/2 ×/)).toBeTruthy();
  expect(screen.queryByRole("img")).toBeNull();
  const negative = container.querySelectorAll('[data-negative="true"]');
  expect(negative.length).toBe(2);
  expect(negative[1]!.textContent).toContain("Profit");
  expect(screen.getByText("+")).toBeTruthy();
});
