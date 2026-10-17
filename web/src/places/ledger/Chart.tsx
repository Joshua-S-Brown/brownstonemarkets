import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ReferenceLine,
} from "recharts";
import type { components } from "../../api/schema";
import { moneyText } from "../../ui/Money";
export function flowRows(rows: components["schemas"]["Day"][]) {
  return rows.map((r) => ({ ...r, out_copper: -r.out_copper }));
}
export function Chart({ rows }: { rows: components["schemas"]["Day"][] }) {
  return (
    <div
      style={{ height: 260 }}
      role="img"
      aria-label="Daily team gold in and out"
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={flowRows(rows)} stackOffset="sign">
          <XAxis dataKey="day" />
          <YAxis tickFormatter={moneyText} />
          <Tooltip formatter={(v) => moneyText(Number(v))} />
          <Legend />
          <ReferenceLine y={0} stroke="var(--fg)" />
          <Bar
            dataKey="in_copper"
            stackId="flow"
            name="Gold in"
            fill="var(--good)"
          />
          <Bar
            dataKey="out_copper"
            stackId="flow"
            name="Gold out"
            fill="var(--bad)"
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
