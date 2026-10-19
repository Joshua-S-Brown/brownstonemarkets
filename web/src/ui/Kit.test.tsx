import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { InspectorContext } from "../app/InspectorContext";
import { PageHead } from "./PageHead";
import { Panel } from "./Panel";
import { Tile } from "./Tile";
import { CharacterName } from "./CharacterName";
import { ConfidencePill } from "./ConfidencePill";
import { SignalPill } from "./SignalPill";
import { Identity } from "./Identity";
import { UtcTime } from "./UtcTime";
import { DataGrid } from "./DataGrid";
import { ItemLink } from "./ItemLink";
import { Money } from "./Money";
import { Kit } from "../places/kit/Kit";
it("PageHead keeps eyebrow, question and optional action", () => {
  render(
    <PageHead
      eyebrow="Scan · 2h"
      title="Today"
      subtitle="What should we do?"
      action={<button>Settings</button>}
    />,
  );
  expect(screen.getByRole("heading", { name: "Today" })).toBeTruthy();
  expect(screen.getByText("What should we do?")).toBeTruthy();
  expect(screen.getByText("Scan · 2h")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Settings" })).toBeTruthy();
});
it("Panel keeps evidence reachable behind its footer", async () => {
  render(
    <Panel
      title="Route"
      subtitle="Cheapest"
      action={<button>Reset</button>}
      evidence={{ recipe_id: 3319 }}
    >
      Answer
    </Panel>,
  );
  expect(screen.getByText("Answer")).toBeTruthy();
  expect(screen.getByText("Cheapest")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Reset" })).toBeTruthy();
  expect(screen.getByText("3319").closest("details")?.open).toBe(false);
  await userEvent.click(screen.getByText("Evidence"));
  expect(screen.getByText("3319").closest("details")?.open).toBe(true);
});
it("Tile hides unknown progress but keeps known zero and clamps the fraction", () => {
  const { rerender } = render(
    <Tile label="Gold" value={<Money copper={null} />} progress={null} />,
  );
  expect(screen.queryByRole("progressbar")).toBeNull();
  expect(screen.getByText("—")).toBeTruthy();
  rerender(<Tile label="Gold" value={<Money copper={0} />} progress={0} />);
  expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe(
    "0",
  );
  expect(screen.getByText("0c").parentElement?.className).toContain("muted");
  rerender(<Tile label="Gold" value="full" progress={2} />);
  expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe(
    "1",
  );
});
it("CharacterName opens the full key, shows only its name and supports initials", async () => {
  const inspect = vi.fn();
  const key: [string, string, string] = ["Maker", "Other realm", "Horde"];
  render(
    <InspectorContext.Provider value={inspect}>
      <CharacterName character={key} avatar />
    </InspectorContext.Provider>,
  );
  const name = screen.getByRole("button", { name: "Maker" });
  expect(name.title).toBe("Other realm · Horde");
  expect(name.textContent).not.toContain("Other realm");
  expect(screen.getByText("MA")).toBeTruthy();
  await userEvent.click(name);
  expect(inspect).toHaveBeenCalledWith({ character: key });
});
it("ConfidencePill maps all confidence tones and exposes every reason", async () => {
  render(
    <>
      <ConfidencePill level="High" reasons={[]} />
      <ConfidencePill level="Medium" reasons={[]} />
      <ConfidencePill level="Low" reasons={["one", "two", "three"]} />
    </>,
  );
  expect(screen.getByText("High").dataset.tone).toBe("good");
  expect(screen.getByText("Medium").dataset.tone).toBe("warn");
  expect(screen.getByText("Low").dataset.tone).toBe("bad");
  await userEvent.hover(screen.getByRole("button", { name: "Low" }));
  expect(await screen.findByRole("tooltip")).toHaveProperty(
    "textContent",
    "one; two; three",
  );
});
it("SignalPill has stable distinct labels and style hooks", () => {
  const labels = [
    "steady",
    "contested",
    "cheap",
    "high",
    "thin",
    "removed early",
  ] as const;
  render(
    <>
      {labels.map((label) => (
        <SignalPill key={label} label={label} />
      ))}
    </>,
  );
  labels.forEach((label) =>
    expect(screen.getByText(label).dataset.signal).toBe(label),
  );
});
it("Identity hides base and lone identities, names variant/unidentified link plainly and explains isolation", async () => {
  render(
    <>
      <Identity state="base" several />
      <Identity state="variant" several />
      <Identity state="unresolved" several />
      <Identity state={null} several />
      <Identity state="variant" several={false} />
    </>,
  );
  expect(screen.queryByText("base")).toBeNull();
  expect(screen.queryByText("unresolved")).toBeNull();
  expect(screen.getAllByText("variant")).toHaveLength(1);
  expect(screen.getByText("legacy")).toBeTruthy();
  await userEvent.hover(screen.getByRole("button", { name: "variant" }));
  expect((await screen.findByRole("tooltip")).textContent).toContain(
    "separate listings and prices",
  );
  await userEvent.unhover(screen.getByRole("button", { name: "variant" }));
  await userEvent.hover(
    screen.getByRole("button", { name: "unidentified link" }),
  );
  await waitFor(() =>
    expect(screen.getByRole("tooltip").textContent).toContain(
      "never enter base-item crafting",
    ),
  );
});
it("UtcTime shows UTC independently of the local zone and retains ISO/local tooltip", () => {
  render(
    <>
      <UtcTime value="2026-10-16T11:37:27Z" />
      <UtcTime value={null} />
    </>,
  );
  const time = screen.getByText("16 Oct 11:37 UTC");
  expect(time.getAttribute("datetime")).toBe("2026-10-16T11:37:27Z");
  expect(time.title).toContain("2026-10-16T11:37:27Z · Local:");
  expect(screen.getByText("unknown")).toBeTruthy();
});
it("DataGrid keeps zero distinct from unknown, tabular alignment and signed percentages", () => {
  render(
    <DataGrid
      density="compact"
      rows={[
        { units: 0, change: -2 },
        { units: null, change: 3 },
      ]}
      columns={[
        {
          accessorKey: "units",
          header: "Units",
          presentation: { numeric: true, mutedZero: true },
        },
        {
          accessorKey: "change",
          header: "Change",
          presentation: { numeric: true, signedPercent: true },
        },
      ]}
    />,
  );
  expect(screen.getByText("unknown")).toBeTruthy();
  expect(screen.getByText("0").className).toContain("muted");
  expect(screen.getByText("0").className).toContain("num");
  expect(screen.getByText("-2%").style.color).toBe("var(--bad)");
  expect(screen.getByText("+3%").style.color).toBe("var(--good)");
  expect(screen.getByRole("table").className).toContain("compact");
});
it("ItemLink initials are local text and preserve exact variant record identity", async () => {
  const inspect = vi.fn();
  render(
    <InspectorContext.Provider value={inspect}>
      <ItemLink
        id={2589}
        name="Linen Cloth"
        badge
        quality={2}
        variant='["variant","key"]'
      />
    </InspectorContext.Provider>,
  );
  expect(screen.getByText("LC")).toBeTruthy();
  await userEvent.click(screen.getByRole("button"));
  expect(inspect).toHaveBeenCalledWith({
    item: 2589,
    variant: '["variant","key"]',
  });
  render(<ItemLink id={2770} name="Ore" badge />);
  expect(screen.getByText("OR")).toBeTruthy();
});
it("kit renders missing prices, at-least counts, no profession, long name, empty and error states", () => {
  render(<Kit />);
  expect(screen.getByText("at least 11")).toBeTruthy();
  expect(screen.getByText(/No profession captured/)).toBeTruthy();
  expect(screen.getByText("A".repeat(40))).toBeTruthy();
  expect(screen.getByRole("alert")).toBeTruthy();
  expect(
    screen.getByRole("heading", { name: "No matching items" }),
  ).toBeTruthy();
});

it("CharacterWords links source-supplied keys in prose without guessing duplicate short names", async () => {
  const { CharacterWords } = await import("./CharacterWords");
  const inspect = vi.fn();
  render(
    <InspectorContext.Provider value={inspect}>
      <CharacterWords
        text="Arille: mail to Maker. Maker · Beta · Alliance"
        characters={[
          ["Arille", "Beta", "Alliance"],
          ["Maker", "Beta", "Alliance"],
          ["Maker", "Other", "Horde"],
        ]}
      />
    </InspectorContext.Provider>,
  );
  await userEvent.click(screen.getByRole("button", { name: "Arille" }));
  expect(inspect).toHaveBeenLastCalledWith({
    character: ["Arille", "Beta", "Alliance"],
  });
  await userEvent.click(screen.getByRole("button", { name: "Maker" }));
  expect(inspect).toHaveBeenLastCalledWith({
    character: ["Maker", "Beta", "Alliance"],
  });
  expect(document.body.textContent).not.toContain("Maker · Beta · Alliance");
  const { PlanText } = await import("../places/today/PlanText");
  render(
    <PlanText text="Craft recipe 3319 (forever-blacksmithing) · Medium confidence (thin listings) · 2s" />,
  );
  expect(screen.getByRole("button", { name: "Medium" })).toBeTruthy();
  expect(screen.queryByText("recipe 3319 (forever-blacksmithing)")).toBeNull();
  await userEvent.click(
    screen.getByRole("button", { name: "recipe evidence" }),
  );
  expect(screen.getByText("recipe 3319 (forever-blacksmithing)")).toBeTruthy();
  expect(screen.getByText("2s")).toBeTruthy();
});
it("SkillBand preserves readable needs/rank and shows catalog colour through a tip", async () => {
  const { SkillBand } = await import("./SkillBand");
  render(
    <SkillBand text="needs 35 · you're 31 · orange 35, yellow 50, green 60, grey 70" />,
  );
  const pill = screen.getByRole("button", { name: "needs 35 · you're 31" });
  await userEvent.tab();
  pill.focus();
  expect(pill.textContent).toBe("needs 35 · you're 31");
  await waitFor(() =>
    expect(screen.getByRole("tooltip").textContent).toContain("yellow 50"),
  );
});
it("compact Route kit keeps numbered stops, item links, ticks and icon-only evidence", async () => {
  const { cleanup } = await import("@testing-library/react");
  cleanup();
  render(
    <InspectorContext.Provider value={vi.fn()}>
      <Kit />
    </InspectorContext.Provider>,
  );
  const tick = screen.getByRole("checkbox", { name: "Example craft" });
  await userEvent.click(tick);
  expect((tick as HTMLInputElement).checked).toBe(true);
  const evidence = screen.getByRole("button", { name: "Line evidence" });
  expect(evidence.textContent?.trim()).toBe("ⓘ");
  await userEvent.click(evidence);
  expect(screen.getByRole("dialog").textContent).toContain("3319");
});
