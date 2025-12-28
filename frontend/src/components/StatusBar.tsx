import { useQuery } from "@tanstack/react-query";
import { fetchStatus } from "../lib/api";
import { formatDistanceToNowStrict } from "../lib/time";

function Pill({ color, text }: { color: string; text: string }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium" style={{ backgroundColor: color }}>
      {text}
    </span>
  );
}

const statusColor: Record<string, string> = {
  running: "#16a34a",
  degraded: "#eab308",
  offline: "#ef4444",
};

export default function StatusBar() {
  const { data } = useQuery({
    queryKey: ["status-bar"],
    queryFn: fetchStatus,
    refetchInterval: 2000,
  });

  const level = data?.status ?? "offline";
  const color = statusColor[level] ?? "#334155";
  const lastFrameAge = data?.last_frame_age ?? null;
  const fps = data?.fps ?? null;
  const temp = data?.temp_c ?? null;
  const disk = data?.disk?.pct_free ?? null;

  return (
    <div className="border-t border-slate-800 bg-slate-950/80">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-4 py-3 text-xs text-slate-200">
        <Pill color={color} text={level.toUpperCase()} />
        <span className="text-slate-400">Last frame: {lastFrameAge != null ? formatDistanceToNowStrict(lastFrameAge) : "—"}</span>
        <span className="text-slate-400">FPS: {fps != null ? fps.toFixed(1) : "—"}</span>
        <span className="text-slate-400">Temp: {temp != null ? `${temp.toFixed(1)}°C` : "—"}</span>
        <span className="text-slate-400">Disk free: {disk != null ? `${disk.toFixed(1)}%` : "—"}</span>
      </div>
    </div>
  );
}

