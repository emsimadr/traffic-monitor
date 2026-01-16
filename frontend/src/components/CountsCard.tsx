import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

type Props = {
  today: number;
  directions: Record<string, number>;
  classes: Record<string, number>;
  fps: number | null;
  lastFrameAge: number | null;
};

export function CountsCard({ today, directions, classes, fps, lastFrameAge }: Props) {
  const dirEntries = Object.entries(directions);
  const classEntries = Object.entries(classes).sort((a, b) => b[1] - a[1]); // Sort by count desc
  
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-lg">Counts</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Today total - big number */}
        <div className="rounded-lg bg-gradient-to-br from-blue-600/20 to-blue-800/20 border border-blue-500/30 p-4 text-center">
          <div className="text-xs uppercase tracking-wide text-blue-300/80">Today</div>
          <div className="text-4xl font-bold text-blue-100">{today}</div>
        </div>

        {/* By direction */}
        {dirEntries.length > 0 && (
          <div className="space-y-2">
            <div className="text-xs text-slate-400 uppercase tracking-wide">By Direction</div>
            <div className="grid grid-cols-2 gap-2">
              {dirEntries.map(([label, count], idx) => (
                <DirectionStat
                  key={label}
                  label={label}
                  value={count}
                  color={idx === 0 ? "cyan" : "orange"}
                />
              ))}
            </div>
          </div>
        )}

        {/* By class (modal split) */}
        {classEntries.length > 0 && (
          <div className="space-y-2">
            <div className="text-xs text-slate-400 uppercase tracking-wide">By Class</div>
            <div className="space-y-1">
              {classEntries.slice(0, 5).map(([className, count]) => (
                <ClassBar key={className} className={className} count={count} total={today} />
              ))}
            </div>
          </div>
        )}

        {/* FPS and frame age */}
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-2">
            <div className="text-xs text-slate-500">FPS</div>
            <div className="font-medium">{fps?.toFixed(1) ?? "—"}</div>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-2">
            <div className="text-xs text-slate-500">Frame Age</div>
            <div className="font-medium">
              {lastFrameAge != null ? `${lastFrameAge.toFixed(1)}s` : "—"}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function DirectionStat({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: "cyan" | "orange";
}) {
  const colors = {
    cyan: "border-cyan-500/30 bg-cyan-900/20 text-cyan-100",
    orange: "border-orange-500/30 bg-orange-900/20 text-orange-100",
  };

  return (
    <div className={`rounded-lg border p-3 ${colors[color]}`}>
      <div className="text-xs opacity-70 truncate">{label}</div>
      <div className="text-xl font-semibold">{value}</div>
    </div>
  );
}

function ClassBar({
  className,
  count,
  total,
}: {
  className: string;
  count: number;
  total: number;
}) {
  const percentage = total > 0 ? (count / total) * 100 : 0;
  const color = getClassColor(className);

  return (
    <div className="flex items-center gap-2">
      <div className="w-20 text-xs text-slate-400 truncate">{className}</div>
      <div className="flex-1 h-5 rounded-full bg-slate-800/50 overflow-hidden">
        <div
          className={`h-full ${color} transition-all duration-300`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <div className="w-12 text-xs text-slate-300 text-right">{count}</div>
    </div>
  );
}

function getClassColor(className: string): string {
  const colors: Record<string, string> = {
    car: "bg-blue-500",
    truck: "bg-blue-600",
    bus: "bg-blue-700",
    bicycle: "bg-green-500",
    motorcycle: "bg-green-600",
    person: "bg-amber-500",
    pedestrian: "bg-amber-500",
    unclassified: "bg-slate-600",
  };
  return colors[className.toLowerCase()] || "bg-slate-500";
}
