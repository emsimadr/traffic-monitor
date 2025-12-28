import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchCalibration, fetchStats, fetchStatus } from "../lib/api";
import { LiveFeed } from "../components/LiveFeed";
import { CountsCard } from "../components/CountsCard";
import { AlertsList } from "../components/AlertsList";
import { RecentEvents } from "../components/RecentEvents";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { formatDistanceToNowStrict } from "../lib/time";

export default function Dashboard() {
  const statusQuery = useQuery({ queryKey: ["status"], queryFn: fetchStatus, refetchInterval: 2000 });
  const statsQuery = useQuery({ queryKey: ["stats"], queryFn: fetchStats, refetchInterval: 5000 });
  const calQuery = useQuery({ queryKey: ["calibration"], queryFn: fetchCalibration, refetchInterval: 10000 });

  const today = statsQuery.data?.last_24h ?? null;
  const last15 = statusQuery.data?.stats?.last_hour ?? null; // proxy for short-term
  const rate = last15 != null ? last15 / 15 : null;
  const directions = statsQuery.data?.last_24h_by_direction ?? {};
  const alerts = statusQuery.data?.alerts ?? [];
  const line = useMemo(() => {
    const l = calQuery.data?.detection?.counting_line;
    if (Array.isArray(l) && l.length === 2) {
      return l.map((p: number[]) => ({ x: p[0], y: p[1] }));
    }
    return null;
  }, [calQuery.data]);

  const recentEvents = useMemo(() => {
    const evts: string[] = [];
    if (statusQuery.data?.last_frame_age != null) {
      evts.push(`Last frame ${formatDistanceToNowStrict(statusQuery.data.last_frame_age)}`);
    }
    if (statusQuery.data?.fps != null) {
      evts.push(`FPS ${statusQuery.data.fps.toFixed(1)}`);
    }
    return evts;
  }, [statusQuery.data]);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card>
            <CardHeader className="flex items-center justify-between">
              <CardTitle>Live</CardTitle>
              <div className="text-xs text-slate-400">/api/camera/live.mjpg</div>
            </CardHeader>
            <CardContent>
              <LiveFeed line={line} />
            </CardContent>
          </Card>
        </div>
        <CountsCard today={today} last15={last15} rate={rate} directions={directions} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <AlertsList alerts={alerts} />
        <RecentEvents events={recentEvents} />
        <Card>
          <CardHeader>
            <CardTitle>Summary</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-slate-200">
            <div>Uptime: {statusQuery.data?.uptime_seconds != null ? formatDuration(statusQuery.data.uptime_seconds) : "—"}</div>
            <div>Last frame age: {statusQuery.data?.last_frame_age != null ? formatDistanceToNowStrict(statusQuery.data.last_frame_age) : "—"}</div>
            <div>Disk free: {statusQuery.data?.disk?.pct_free != null ? `${statusQuery.data.disk.pct_free.toFixed(1)}%` : "—"}</div>
            <div>Temp: {statusQuery.data?.temp_c != null ? `${statusQuery.data.temp_c.toFixed(1)}°C` : "—"}</div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function formatDuration(seconds: number) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

