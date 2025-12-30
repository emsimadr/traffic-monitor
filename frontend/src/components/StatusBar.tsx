import { useQuery } from "@tanstack/react-query";
import { fetchCompactStatus } from "../lib/api";

function Pill({ running }: { running: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
        running
          ? "bg-green-500/20 text-green-400"
          : "bg-red-500/20 text-red-400"
      }`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          running ? "bg-green-400" : "bg-red-400"
        }`}
      />
      {running ? "RUNNING" : "OFFLINE"}
    </span>
  );
}

export default function StatusBar() {
  const { data } = useQuery({
    queryKey: ["status-bar"],
    queryFn: fetchCompactStatus,
    refetchInterval: 2000,
  });

  const running = data?.running ?? false;
  const lastFrameAge = data?.last_frame_age_s ?? null;
  const fps = data?.fps_capture ?? null;
  const temp = data?.cpu_temp_c ?? null;
  const disk = data?.disk_free_pct ?? null;
  const countsToday = data?.counts_today_total ?? 0;
  const warnings = data?.warnings ?? [];

  return (
    <div className="border-t border-slate-800 bg-slate-950/60">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-4 py-2 text-xs">
        <Pill running={running} />
        
        <Stat label="Frame" value={lastFrameAge != null ? `${lastFrameAge.toFixed(1)}s` : "—"} />
        <Stat label="FPS" value={fps != null ? fps.toFixed(1) : "—"} />
        <Stat label="Temp" value={temp != null ? `${temp.toFixed(0)}°C` : "—"} warn={temp != null && temp > 70} />
        <Stat label="Disk" value={disk != null ? `${disk.toFixed(0)}%` : "—"} warn={disk != null && disk < 20} />
        <Stat label="Today" value={String(countsToday)} highlight />

        {warnings.length > 0 && (
          <span className="text-amber-400">
            ⚠ {warnings.length} warning{warnings.length > 1 ? "s" : ""}
          </span>
        )}
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  warn,
  highlight,
}: {
  label: string;
  value: string;
  warn?: boolean;
  highlight?: boolean;
}) {
  return (
    <span className={`text-slate-400 ${warn ? "text-amber-400" : ""} ${highlight ? "text-blue-400" : ""}`}>
      {label}: <span className="text-slate-200">{value}</span>
    </span>
  );
}
