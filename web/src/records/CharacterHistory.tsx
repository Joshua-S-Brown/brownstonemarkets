import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { UtcTime, utcLabel } from "../ui/UtcTime";
export function CharacterHistory({
  rows,
}: {
  rows: Record<string, unknown>[];
}) {
  const series = [...new Set(rows.map((r) => String(r.Series)))];
  return (
    <>
      <h2>Progress over time</h2>
      {rows.length ? (
        <ResponsiveContainer width="100%" height={260}>
          <LineChart>
            <XAxis
              tickFormatter={(v) => utcLabel(String(v))}
              dataKey="UTC"
              type="category"
              allowDuplicatedCategory={false}
            />
            <YAxis />
            <Tooltip labelFormatter={(v) => utcLabel(String(v)) + " UTC"} />
            <Legend />
            {series.map((s, i) => (
              <Line
                key={s}
                stroke={`var(--chart-${(i % 10) + 1})`}
                name={s}
                data={rows.filter((r) => r.Series === s)}
                dataKey="Value"
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <table>
          <thead>
            <tr>
              <th>UTC</th>
              <th>Series</th>
              <th>Value</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td colSpan={3}>No readable level or rank history yet.</td>
            </tr>
          </tbody>
        </table>
      )}
      <details>
        <summary>All readings</summary>
        <table>
          <thead>
            <tr>
              <th>UTC</th>
              <th>Series</th>
              <th>Value</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td>
                  <UtcTime value={String(r.UTC)} />
                </td>
                <td>{String(r.Series)}</td>
                <td>{String(r.Value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </>
  );
}
