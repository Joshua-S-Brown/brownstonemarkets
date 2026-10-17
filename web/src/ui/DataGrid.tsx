import { useState } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { UtcTime } from "./UtcTime";
import kit from "./components.module.css";
import styles from "../theme/app.module.css";
type Presentation = {
  numeric?: boolean;
  signedPercent?: boolean;
  mutedZero?: boolean;
};
export type GridColumn<T> = ColumnDef<T> & { presentation?: Presentation };
export function DataGrid<T>({
  rows,
  columns,
  selected,
  density = "normal",
}: {
  rows: T[];
  columns: GridColumn<T>[];
  density?: "normal" | "compact";
  selected?: (row: T) => boolean;
}) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const table = useReactTable({
    defaultColumn: { cell: ({ getValue }) => String(getValue() ?? "unknown") },
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 30 } },
  });
  return (
    <>
      <div className={`${kit["table-wrap"]} ${styles["grid-scroll"]}`}>
        <table className={density === "compact" ? kit.compact : undefined}>
          <thead>
            {table.getHeaderGroups().map((g) => (
              <tr key={g.id}>
                {g.headers.map((h) => (
                  <th
                    className={
                      (h.column.columnDef as GridColumn<T>).presentation
                        ?.numeric
                        ? kit.num
                        : undefined
                    }
                    key={h.id}
                    aria-sort={
                      h.column.getIsSorted() === "asc"
                        ? "ascending"
                        : h.column.getIsSorted() === "desc"
                          ? "descending"
                          : "none"
                    }
                  >
                    <button
                      disabled={!h.column.getCanSort()}
                      onClick={h.column.getToggleSortingHandler()}
                    >
                      {flexRender(h.column.columnDef.header, h.getContext())}
                      {h.column.getIsSorted() === "asc"
                        ? " ↑"
                        : h.column.getIsSorted() === "desc"
                          ? " ↓"
                          : ""}
                    </button>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((r) => (
              <tr key={r.id} data-selected={selected?.(r.original)}>
                {r.getVisibleCells().map((c) => (
                  <td
                    key={c.id}
                    className={`${(c.column.columnDef as GridColumn<T>).presentation?.numeric || typeof c.getValue() === "number" ? kit.num : ""} ${c.getValue() === 0 && (c.column.columnDef as GridColumn<T>).presentation?.mutedZero ? kit.muted : ""}`}
                    style={
                      (c.column.columnDef as GridColumn<T>).presentation
                        ?.signedPercent
                        ? {
                            color:
                              Number(c.getValue()) > 0
                                ? "var(--good)"
                                : Number(c.getValue()) < 0
                                  ? "var(--bad)"
                                  : "var(--muted)",
                          }
                        : undefined
                    }
                  >
                    {(c.column.columnDef as GridColumn<T>).presentation
                      ?.signedPercent ? (
                      c.getValue() == null ? (
                        "unknown"
                      ) : (
                        `${Number(c.getValue()) > 0 ? "+" : ""}${c.getValue()}%`
                      )
                    ) : typeof c.getValue() === "string" &&
                      /^\d{4}-\d\d-\d\dT\d\d:/.test(c.getValue() as string) ? (
                      <UtcTime value={c.getValue() as string} />
                    ) : c.getValue() == null && !c.column.columnDef.cell ? (
                      "unknown"
                    ) : (
                      flexRender(c.column.columnDef.cell, c.getContext())
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className={styles["grid-tools"]}>
        <button
          disabled={!table.getCanPreviousPage()}
          onClick={() => table.previousPage()}
        >
          Previous
        </button>
        <span>
          {rows.length} rows · page {table.getState().pagination.pageIndex + 1}{" "}
          of {Math.max(1, table.getPageCount())}
        </span>
        <button
          disabled={!table.getCanNextPage()}
          onClick={() => table.nextPage()}
        >
          Next
        </button>
      </div>
    </>
  );
}
