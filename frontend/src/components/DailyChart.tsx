import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { DailyCount } from "../lib/api";

type Props = {
  data: DailyCount[];
  classFilter: Set<string>;
};

export function DailyChart({ data, classFilter }: Props) {
  // Transform data for Recharts
  const chartData = data.map((day) => {
    // Sum counts for filtered classes
    let total = 0;
    for (const [className, count] of Object.entries(day.by_class)) {
      if (classFilter.size === 0 || classFilter.has(className)) {
        total += count;
      }
    }

    return {
      date: day.date,
      count: total,
    };
  });

  if (chartData.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-slate-500">
        No data available
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f2a37" />
        <XAxis
          dataKey="date"
          stroke="#9fb0c3"
          tick={{ fill: "#9fb0c3", fontSize: 12 }}
          interval="preserveStartEnd"
        />
        <YAxis stroke="#9fb0c3" tick={{ fill: "#9fb0c3", fontSize: 12 }} />
        <Tooltip
          contentStyle={{
            backgroundColor: "#111827",
            border: "1px solid #1f2a37",
            borderRadius: "8px",
            color: "#e8eef6",
          }}
        />
        <Legend wrapperStyle={{ color: "#9fb0c3" }} />
        <Line
          type="monotone"
          dataKey="count"
          stroke="#2563eb"
          strokeWidth={2}
          dot={{ fill: "#2563eb", r: 3 }}
          name="Counts"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

