import { Money } from "./Money";
import styles from "../theme/app.module.css";
export function evidenceLabel(key: string) {
  const words = key.replace(/_copper$/, "").replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}
// Stored metric fields that hold integer copper without the _copper suffix.
const COPPER = new Set([
  "copper",
  "min_buyout",
  "market_value",
  "buyout",
  "unit_buyout",
]);
const copperField = (name: string) =>
  name.endsWith("_copper") || COPPER.has(name);
function Value({ name, value }: { name: string; value: unknown }) {
  if (value === null || value === undefined || value === "")
    return (
      <span className={styles["muted"]}>
        {/(error|warning|note)$/.test(name) ? "none" : "unknown"}
      </span>
    );
  if (copperField(name) && typeof value === "number")
    return <Money copper={value} />;
  if (typeof value === "boolean") return <>{value ? "yes" : "no"}</>;
  if (Array.isArray(value)) {
    if (value.length === 0)
      return <span className={styles["muted"]}>none</span>;
    if (value.every((v) => v === null || typeof v !== "object"))
      return (
        <>{value.map((v) => (v === null ? "unknown" : String(v))).join(", ")}</>
      );
    if (value.every(flat))
      return <EvidenceTable rows={value as Record<string, unknown>[]} />;
    return (
      <ol className={styles["evidence-list"]}>
        {value.map((v, i) => (
          <li key={i}>
            <Value name={name} value={v} />
          </li>
        ))}
      </ol>
    );
  }
  if (typeof value === "object") return <Evidence data={value} />;
  return (
    <>
      {typeof value === "number" && !/(^|_)id$/.test(name)
        ? value.toLocaleString("en-US")
        : String(value)}
    </>
  );
}
function flat(v: unknown) {
  return (
    v !== null &&
    typeof v === "object" &&
    !Array.isArray(v) &&
    Object.values(v).every(
      (x) =>
        x === null ||
        typeof x !== "object" ||
        (Array.isArray(x) &&
          x.every((y) => y === null || typeof y !== "object")),
    )
  );
}
/** Records of plain facts read as rows, with every key any row has as a column. */
function EvidenceTable({ rows }: { rows: Record<string, unknown>[] }) {
  const keys = [...new Set(rows.flatMap((r) => Object.keys(r)))];
  return (
    <div className={styles["grid-scroll"]}>
      <table className={styles["evidence-table"]}>
        <thead>
          <tr>
            {keys.map((k) => (
              <th key={k}>{evidenceLabel(k)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {keys.map((k) => (
                <td key={k}>
                  <Value name={k} value={r[k]} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
/** Every stored evidence field stays visible, labelled instead of dumped as JSON; null stays unknown, never 0. */
export function Evidence({ data }: { data: object }) {
  return (
    <dl className={styles["evidence-list"]}>
      {Object.entries(data).map(([key, value]) => (
        <div key={key}>
          <dt>{evidenceLabel(key)}</dt>
          <dd>
            <Value name={key} value={value} />
          </dd>
        </div>
      ))}
    </dl>
  );
}
