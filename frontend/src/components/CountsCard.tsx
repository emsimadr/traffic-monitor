import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

type Props = {
  today: number;
  directions: Record<string, number>;
  fps: number | null;
  lastFrameAge: number | null;
};

export function CountsCard({ today, directions, fps, lastFrameAge }: Props) {
  const dirEntries = Object.entries(directions);
  
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
