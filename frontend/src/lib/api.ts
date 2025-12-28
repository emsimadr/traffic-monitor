export type StatusLevel = "running" | "degraded" | "offline";

export interface StatusResponse {
  status: StatusLevel;
  alerts: string[];
  last_frame_age: number | null;
  fps: number | null;
  uptime_seconds: number | null;
  disk: {
    total_bytes: number | null;
    used_bytes: number | null;
    free_bytes: number | null;
    pct_free: number | null;
  };
  temp_c: number | null;
  stats: StatsSummary;
  health: Record<string, unknown>;
  timestamp: number;
}

export interface StatsSummary {
  total_detections: number;
  last_hour: number;
  last_24h: number;
  last_24h_by_direction: Record<string, number>;
}

export interface HealthResponse {
  [key: string]: unknown;
}

const json = async <T>(url: string, init?: RequestInit): Promise<T> => {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
};

export const fetchStatus = () => json<StatusResponse>("/api/status");
export const fetchStats = () => json<StatsSummary>("/api/stats/summary");
export const fetchHealth = () => json<HealthResponse>("/api/health");

export const fetchConfig = () => json<any>("/api/config"); // existing API expects POST for save
export const saveConfig = (overrides: any) =>
  json<{ ok: boolean }>("/api/config", {
    method: "POST",
    body: JSON.stringify({ overrides }),
  });

export const fetchCalibration = () => json<any>("/api/calibration");
export const saveCalibration = (payload: any) =>
  json<{ ok: boolean }>("/api/calibration", {
    method: "POST",
    body: JSON.stringify(payload),
  });

