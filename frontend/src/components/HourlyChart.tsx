import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { HourlyCount } from "../lib/api";

type Props = {
  data: HourlyCount[];
  classFilter: Set<string>;
};

export function HourlyChart({ data, classFilter }: Props) {
  // Transform data for Recharts (group by hour, sum filtered classes)
  const chartData = data.map((hour) => {
    const hourLabel = new Date(hour.hour_start_ts * 1000).toLocaleDateString(
      "en-US",
      { month: "short", day: "numeric", hour: "2-digit" }
    );

    // Sum counts for filtered classes
    let total = 0;
    for (const [className, count] of Object.entries(hour.by_class)) {
      if (classFilter.size === 0 || classFilter.has(className)) {
        total += count;
      }
    }

    return {
      hour: hourLabel,
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
      <BarChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f2a37" />
        <XAxis
          dataKey="hour"
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
        <Bar dataKey="count" fill="#2563eb" name="Counts" />
      </BarChart>
    </ResponsiveContainer>
  );
}

