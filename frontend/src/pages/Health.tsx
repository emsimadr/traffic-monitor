import { useQuery } from "@tanstack/react-query";
import { fetchHealth, fetchStatus } from "../lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { formatDistanceToNowStrict } from "../lib/time";

export default function Health() {
  const statusQuery = useQuery({ queryKey: ["status-health"], queryFn: fetchStatus, refetchInterval: 5000 });
  const healthQuery = useQuery({ queryKey: ["health"], queryFn: fetchHealth, refetchInterval: 5000 });

  const lastFrameAge = statusQuery.data?.last_frame_age ?? null;
  const fps = statusQuery.data?.fps ?? null;
  const temp = statusQuery.data?.temp_c ?? null;
  const disk = statusQuery.data?.disk?.pct_free ?? null;
  const uptime = statusQuery.data?.uptime_seconds ?? null;

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
      <HealthCard title="CPU Temp" value={temp != null ? `${temp.toFixed(1)}°C` : "—"} />
      <HealthCard title="Disk free" value={disk != null ? `${disk.toFixed(1)}%` : "—"} />
      <HealthCard title="FPS" value={fps != null ? fps.toFixed(1) : "—"} />
      <HealthCard title="Last frame age" value={lastFrameAge != null ? formatDistanceToNowStrict(lastFrameAge) : "—"} />
      <HealthCard title="Uptime" value={uptime != null ? formatUptime(uptime) : "—"} />
      <HealthCard title="Platform" value={String(healthQuery.data?.platform ?? "—")} />
      <HealthCard title="Python" value={String(healthQuery.data?.python ?? "—")} />
      <HealthCard title="Storage path" value={String(healthQuery.data?.storage_db_path ?? "—")} />
    </div>
  );
}

function HealthCard({ title, value }: { title: string; value: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="text-lg font-semibold">{value}</CardContent>
    </Card>
  );
}

function formatUptime(seconds: number) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

