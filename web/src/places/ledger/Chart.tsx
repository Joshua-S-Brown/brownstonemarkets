import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
} from "recharts";
import type { components } from "../../api/schema";
import { moneyText } from "../../ui/Money";
export function Chart({ rows }: { rows: components["schemas"]["Day"][] }) {
  return (
    <div
      style={{ height: 260 }}
      role="img"
      aria-label="Daily team gold in and out"
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows}>
          <XAxis dataKey="day" />
          <YAxis tickFormatter={moneyText} />
          <Tooltip formatter={(v) => moneyText(Number(v))} />
          <Legend />
          <Bar dataKey="in_copper" name="Gold in" fill="var(--good)" />
          <Bar dataKey="out_copper" name="Gold out" fill="var(--warn)" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
