import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

type Props = {
  today: number | null;
  last15: number | null;
  rate: number | null;
  directions: Record<string, number>;
};

export function CountsCard({ today, last15, rate, directions }: Props) {
  return (
    <Card>
      <CardHeader className="mb-3 flex justify-between">
        <CardTitle>Counters</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-3 gap-3 text-sm">
          <Stat label="Today" value={today} />
          <Stat label="Last 15m" value={last15} />
          <Stat label="Rate (per min)" value={rate != null ? rate.toFixed(2) : null} />
        </div>
        <div>
          <div className="text-xs text-slate-400">Direction</div>
          <div className="mt-2 grid grid-cols-3 gap-2 text-sm">
            {Object.entries(directions || {}).map(([k, v]) => (
              <Stat key={k} label={k} value={v} />
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: number | string | null }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/80 p-3">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="text-lg font-semibold">{value ?? "—"}</div>
    </div>
  );
}

