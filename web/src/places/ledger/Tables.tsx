import { UtcTime } from "../../ui/UtcTime";
import { CharacterName } from "../../ui/CharacterName";
import { DataGrid } from "../../ui/DataGrid";
import { ItemLink } from "../../ui/ItemLink";
import { Money } from "../../ui/Money";
import { Pill } from "../../ui/parts";
import type { components } from "../../api/schema";
export function GoldPairs({
  rows,
}: {
  rows: components["schemas"]["GoldPair"][];
}) {
  return (
    <DataGrid
      rows={rows}
      columns={[
        {
          accessorKey: "character",
          header: "Character",
          cell: ({ row: { original: r } }) => (
            <CharacterName character={r.character} />
          ),
        },
        {
          accessorKey: "from_utc",
          header: "From UTC",
          cell: ({ row: { original: r } }) => <UtcTime value={r.from_utc} />,
        },
        {
          accessorKey: "to_utc",
          header: "To UTC",
          cell: ({ row: { original: r } }) => <UtcTime value={r.to_utc} />,
        },
        ...["actual_copper", "recorded_copper", "unexplained_copper"].map(
          (k) => ({
            accessorKey: k,
            header: k.replace("_copper", ""),
            cell: ({
              row: { original: r },
            }: {
              row: { original: components["schemas"]["GoldPair"] };
            }) => <Money copper={r[k as "actual_copper"]} />,
          }),
        ),
        { accessorKey: "reason", header: "Reason" },
      ]}
    />
  );
}
export function Residuals({
  rows,
  names,
}: {
  rows: components["schemas"]["ItemResidual"][];
  names: Record<string, string>;
}) {
  return (
    <DataGrid
      rows={rows}
      columns={[
        {
          accessorKey: "character",
          header: "Character",
          cell: ({ row: { original: r } }) => (
            <CharacterName character={r.character} />
          ),
        },
        {
          accessorKey: "item_id",
          header: "Item",
          cell: ({ row: { original: r } }) => (
            <ItemLink
              id={r.item_id}
              name={names[r.item_id] ?? `Item ${r.item_id}`}
            />
          ),
        },
        { accessorKey: "kind", header: "Location" },
        { accessorKey: "residual_units", header: "Residual units" },
        { accessorKey: "actual_units", header: "Actual units" },
        { accessorKey: "recorded_units", header: "Recorded units" },
        {
          accessorKey: "from_utc",
          header: "From UTC",
          cell: ({ row: { original: r } }) => <UtcTime value={r.from_utc} />,
        },
        {
          accessorKey: "to_utc",
          header: "To UTC",
          cell: ({ row: { original: r } }) => <UtcTime value={r.to_utc} />,
        },
        {
          accessorKey: "possibly_incomplete",
          header: "Evidence",
          cell: ({ row: { original: r } }) =>
            r.possibly_incomplete ? (
              <Pill tone="warn">possibly incomplete</Pill>
            ) : null,
        },
      ]}
    />
  );
}
