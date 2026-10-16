import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { Evidence } from "../ui/Evidence";
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
              dataKey="UTC"
              type="category"
              allowDuplicatedCategory={false}
            />
            <YAxis />
            <Tooltip />
            <Legend />
            {series.map((s) => (
              <Line
                key={s}
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
      <Evidence data={{ history: rows }} />
    </>
  );
}
