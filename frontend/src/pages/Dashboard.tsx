import { useMemo, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchCompactStatus } from "../lib/api";
import { LiveFeed } from "../components/LiveFeed";
import { CountsCard } from "../components/CountsCard";
import { AlertsList } from "../components/AlertsList";
import { RecentEventsTable } from "../components/RecentEventsTable";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";

export default function Dashboard() {
  // Poll compact status every 2 seconds
  const statusQuery = useQuery({
    queryKey: ["compact-status"],
    queryFn: fetchCompactStatus,
    refetchInterval: 2000,
  });

  const data = statusQuery.data;

  // Extract values from compact status
  const countsToday = data?.counts_today_total ?? 0;
  const fps = data?.fps_capture ?? null;
  const warnings = data?.warnings ?? [];
  const lastFrameAge = data?.last_frame_age_s ?? null;
  const running = data?.running ?? false;

  // Map direction codes to labels
  const directions = useMemo(() => {
    if (!data) return {};
    const counts = data.counts_by_direction_code || {};
    const labels = data.direction_labels || {};

    const result: Record<string, number> = {};
    for (const [code, count] of Object.entries(counts)) {
      const label = labels[code] || code;
      result[label] = count;
    }
    return result;
  }, [data]);

  // Class distribution (modal split)
  const classes = data?.counts_by_class ?? {};

  // Browser notifications for critical warnings
  useEffect(() => {
    if (!("Notification" in window)) return;
    
    if (Notification.permission === "default") {
      Notification.requestPermission();
    }
    
    if (Notification.permission === "granted" && warnings.includes("camera_offline")) {
      new Notification("Traffic Monitor Alert", {
        body: "Camera offline for more than 10 seconds",
        icon: "/favicon.ico",
        tag: "camera-offline", // Prevent duplicate notifications
      });
    }
  }, [warnings]);

  return (
    <div className="space-y-4">
      {/* Status indicator */}
      <div className="flex items-center gap-2 text-sm">
        <div
          className={`h-2 w-2 rounded-full ${
            running ? "bg-green-500" : "bg-red-500"
          }`}
        />
        <span className={running ? "text-green-400" : "text-red-400"}>
          {running ? "Running" : "Offline"}
        </span>
        {fps != null && (
          <span className="text-slate-400">• {fps.toFixed(1)} FPS</span>
        )}
        {lastFrameAge != null && (
          <span className="text-slate-400">
            • Frame age: {lastFrameAge.toFixed(1)}s
          </span>
        )}
      </div>

      {/* Main content grid */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Live feed - takes 2 columns on large screens */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-lg">Live Feed</CardTitle>
              <span className="text-xs text-slate-500">/api/camera/live.mjpg</span>
            </CardHeader>
            <CardContent className="p-0">
              <LiveFeed />
            </CardContent>
          </Card>
        </div>

        {/* Counts card */}
        <CountsCard
          today={countsToday}
          directions={directions}
          classes={classes}
          fps={fps}
          lastFrameAge={lastFrameAge}
        />
      </div>

      {/* Bottom row */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {/* Recent Events */}
        <RecentEventsTable />

        {/* Alerts */}
        <AlertsList alerts={warnings} />

        {/* System stats */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">System</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <StatRow
              label="CPU Temp"
              value={data?.cpu_temp_c != null ? `${data.cpu_temp_c.toFixed(1)}°C` : "—"}
              warn={data?.cpu_temp_c != null && data.cpu_temp_c > 70}
            />
            <StatRow
              label="Disk Free"
              value={data?.disk_free_pct != null ? `${data.disk_free_pct.toFixed(1)}%` : "—"}
              warn={data?.disk_free_pct != null && data.disk_free_pct < 20}
            />
            <StatRow
              label="Inference"
              value={
                data?.fps_infer != null
                  ? `${data.fps_infer.toFixed(1)} FPS`
                  : "N/A"
              }
            />
            <StatRow
              label="Latency (p50)"
              value={
                data?.infer_latency_ms_p50 != null
                  ? `${data.infer_latency_ms_p50.toFixed(0)}ms`
                  : "N/A"
              }
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function StatRow({
  label,
  value,
  warn,
}: {
  label: string;
  value: string;
  warn?: boolean;
}) {
  return (
    <div className="flex justify-between">
      <span className="text-slate-400">{label}</span>
      <span className={warn ? "text-amber-400" : ""}>{value}</span>
    </div>
  );
}
