import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

const labels: Record<string, string> = {
  camera_offline: "Camera offline",
  camera_stale: "Camera stale",
  disk_low: "Low disk",
  temp_high: "High temperature",
};

export function AlertsList({ alerts }: { alerts: string[] }) {
  const items = alerts && alerts.length ? alerts : [];
  return (
    <Card>
      <CardHeader>
        <CardTitle>Alerts</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {items.length === 0 ? (
          <div className="text-slate-400">No alerts</div>
        ) : (
          items.map((a) => (
            <div key={a} className="rounded border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-amber-100">
              {labels[a] ?? a}
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

