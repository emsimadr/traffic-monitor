import { useQuery } from "@tanstack/react-query";
import { fetchHealth, fetchCompactStatus } from "../lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";

export default function Health() {
  const statusQuery = useQuery({
    queryKey: ["compact-status-health"],
    queryFn: fetchCompactStatus,
    refetchInterval: 5000,
  });
  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 10000,
  });

  const status = statusQuery.data;
  const health = healthQuery.data;

  const lastFrameAge = status?.last_frame_age_s ?? null;
  const fps = status?.fps_capture ?? null;
  const temp = status?.cpu_temp_c ?? null;
  const disk = status?.disk_free_pct ?? null;
  const running = status?.running ?? false;
  const warnings = status?.warnings ?? [];

  return (
    <div className="space-y-6">
      {/* Overall status */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-3">
            System Status
            <Badge variant={running ? "default" : "destructive"}>
              {running ? "Running" : "Offline"}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {warnings.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {warnings.map((w) => (
                <Badge key={w} variant="outline" className="border-amber-500/50 text-amber-400">
                  {warningLabels[w] ?? w}
                </Badge>
              ))}
            </div>
          ) : (
            <div className="text-green-400 text-sm">All systems nominal</div>
          )}
        </CardContent>
      </Card>

      {/* Metrics grid */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
        <HealthCard
          title="CPU Temperature"
          value={temp != null ? `${temp.toFixed(1)}°C` : "—"}
          status={getStatus(temp, { warn: 70, crit: 80 })}
        />
        <HealthCard
          title="Disk Free"
          value={disk != null ? `${disk.toFixed(1)}%` : "—"}
          status={getStatusReverse(disk, { warn: 20, crit: 10 })}
        />
        <HealthCard
          title="Capture FPS"
          value={fps != null ? fps.toFixed(1) : "—"}
          status={fps != null && fps > 0 ? "ok" : "crit"}
        />
        <HealthCard
          title="Frame Age"
          value={lastFrameAge != null ? `${lastFrameAge.toFixed(1)}s` : "—"}
          status={getStatus(lastFrameAge, { warn: 2, crit: 10 })}
        />
        <HealthCard
          title="Inference FPS"
          value={status?.fps_infer != null ? status.fps_infer.toFixed(1) : "N/A"}
        />
        <HealthCard
          title="Latency (p50)"
          value={status?.infer_latency_ms_p50 != null ? `${status.infer_latency_ms_p50.toFixed(0)}ms` : "N/A"}
        />
        <HealthCard
          title="Latency (p95)"
          value={status?.infer_latency_ms_p95 != null ? `${status.infer_latency_ms_p95.toFixed(0)}ms` : "N/A"}
        />
        <HealthCard
          title="Today Counts"
          value={String(status?.counts_today_total ?? 0)}
        />
      </div>

      {/* System info */}
      <Card>
        <CardHeader>
          <CardTitle>System Information</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 text-sm">
            <InfoRow label="Platform" value={health?.platform} />
            <InfoRow label="Python" value={health?.python} />
            <InfoRow label="Working Directory" value={health?.cwd} />
            <InfoRow label="Database Path" value={health?.storage_db_path} />
            <InfoRow label="Log Path" value={health?.log_path} />
            <InfoRow
              label="Last Update"
              value={
                health?.timestamp
                  ? new Date(health.timestamp * 1000).toLocaleTimeString()
                  : undefined
              }
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

const warningLabels: Record<string, string> = {
  camera_offline: "Camera Offline",
  camera_stale: "Camera Stale",
  disk_low: "Low Disk Space",
  temp_high: "High Temperature",
};

type StatusType = "ok" | "warn" | "crit" | undefined;

function getStatus(
  value: number | null,
  thresholds: { warn: number; crit: number }
): StatusType {
  if (value == null) return undefined;
  if (value >= thresholds.crit) return "crit";
  if (value >= thresholds.warn) return "warn";
  return "ok";
}

function getStatusReverse(
  value: number | null,
  thresholds: { warn: number; crit: number }
): StatusType {
  if (value == null) return undefined;
  if (value <= thresholds.crit) return "crit";
  if (value <= thresholds.warn) return "warn";
  return "ok";
}

function HealthCard({
  title,
  value,
  status,
}: {
  title: string;
  value: string;
  status?: StatusType;
}) {
  const statusColors = {
    ok: "border-green-500/30 bg-green-900/10",
    warn: "border-amber-500/30 bg-amber-900/10",
    crit: "border-red-500/30 bg-red-900/10",
  };

  const valueColors = {
    ok: "text-green-400",
    warn: "text-amber-400",
    crit: "text-red-400",
  };

  return (
    <Card className={status ? statusColors[status] : ""}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-slate-400">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className={`text-2xl font-bold ${status ? valueColors[status] : ""}`}>
          {value}
        </div>
      </CardContent>
    </Card>
  );
}

function InfoRow({ label, value }: { label: string; value?: string | unknown }) {
  return (
    <div className="flex justify-between py-1 border-b border-slate-800/50">
      <span className="text-slate-500">{label}</span>
      <span className="text-slate-200 font-mono text-xs truncate max-w-[60%]">
        {String(value ?? "—")}
      </span>
    </div>
  );
}
