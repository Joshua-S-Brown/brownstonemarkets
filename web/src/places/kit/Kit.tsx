import { PageHead } from "../../ui/PageHead";
import { Panel } from "../../ui/Panel";
import { Tile } from "../../ui/Tile";
import { CharacterName } from "../../ui/CharacterName";
import { ConfidencePill } from "../../ui/ConfidencePill";
import { SignalPill } from "../../ui/SignalPill";
import { Identity } from "../../ui/Identity";
import { UtcTime } from "../../ui/UtcTime";
import { ItemLink } from "../../ui/ItemLink";
import { Money } from "../../ui/Money";
import { DataGrid } from "../../ui/DataGrid";
import { EmptyState, ErrorState, Pill, Tip } from "../../ui/parts";
import styles from "../../ui/components.module.css";
export function Kit() {
  return (
    <div className={styles.showcase}>
      <PageHead
        eyebrow="Shared components · edge-state fixtures"
        title="Component kit"
        subtitle="How does each state look before we build a page around it?"
        action={
          <Tip text="Kit fixtures are illustrative, never market calculations">
            <Pill>Preview</Pill>
          </Tip>
        }
      />
      <div className={styles.kpis}>
        <Tile
          label="Unknown money"
          value={<Money copper={null} />}
          caption="Price missing; never free"
          progress={null}
        />
        <Tile
          label="Zero money"
          value={<Money copper={0} />}
          caption="A real zero"
          progress={0}
        />
        <Tile
          label="Holdings"
          value="at least 11"
          caption="Bank not captured"
        />
        <Tile label="Progress" value="1 / 4" progress={0.25} />
      </div>
      <Panel
        title="Names and identities"
        subtitle="Full keys remain in record links"
        evidence={{
          recipe_id: 3319,
          catalog_id: "forever-blacksmithing",
          rules_version: "example",
          route_reason: "Compatible known route",
        }}
      >
        <CharacterName
          character={["Arille", "Classic Beta PvE 2", "Alliance"]}
          avatar
        />{" "}
        · No profession captured
        <p>
          <ItemLink id={2589} name="Linen Cloth" quality={1} badge />{" "}
          <Identity state="base" />
        </p>
        <p>
          <ItemLink
            id={2578}
            name={"A".repeat(40)}
            variant='["variant","v1:e41:g0,0,0,0:s0:b"]'
            quality={2}
            badge
          />{" "}
          <Identity state="variant" />
        </p>
        <p>
          <Identity state="unresolved" /> <Identity state={null} />
        </p>
        <UtcTime value="2026-10-16T11:37:27Z" />
      </Panel>
      <Panel title="Confidence and signals">
        {(["High", "Medium", "Low"] as const).map((level) => (
          <ConfidencePill
            key={level}
            level={level}
            reasons={[
              "Missing price evidence",
              "Thin listing depth",
              "Recipe learning not captured",
            ]}
          />
        ))}
        <p>
          {(
            [
              "steady",
              "contested",
              "cheap",
              "high",
              "thin",
              "removed early",
            ] as const
          ).map((label) => (
            <SignalPill key={label} label={label} />
          ))}
        </p>
      </Panel>
      <Panel
        title="Numbers"
        subtitle="Compact density, sign colours, zero and missing prices"
      >
        <DataGrid
          density="compact"
          rows={[
            { units: 0, price: null, change: 0 },
            { units: 11, price: 30, change: 12 },
            { units: 3, price: 0, change: -5 },
          ]}
          columns={[
            {
              accessorKey: "units",
              header: "Units",
              presentation: { numeric: true, mutedZero: true },
            },
            {
              accessorKey: "price",
              header: "Price",
              presentation: { numeric: true, mutedZero: true },
              cell: ({ row }) => <Money copper={row.original.price} />,
            },
            {
              accessorKey: "change",
              header: "Change",
              presentation: {
                numeric: true,
                signedPercent: true,
                mutedZero: true,
              },
            },
          ]}
        />
      </Panel>
      <EmptyState title="No matching items">
        Try another name or item ID.
      </EmptyState>
      <ErrorState
        error={
          new Error("Saved scan is unreadable. Open Data to review the source.")
        }
        retry={() => {}}
      />
    </div>
  );
}
