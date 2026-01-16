export type StatusLevel = "running" | "degraded" | "offline";

/**
 * Full status response from /api/status (legacy)
 */
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

/**
 * Compact status response from /api/status/compact (optimized for polling)
 */
export interface CompactStatusResponse {
  running: boolean;
  last_frame_age_s: number | null;
  fps_capture: number | null;
  fps_infer: number | null;
  infer_latency_ms_p50: number | null;
  infer_latency_ms_p95: number | null;
  counts_today_total: number;
  counts_by_direction_code: Record<string, number>;
  counts_by_class: Record<string, number>;
  direction_labels: Record<string, string>;
  cpu_temp_c: number | null;
  disk_free_pct: number | null;
  warnings: string[];
}

export interface CountEvent {
  ts: number;
  direction_code: string;
  direction_label: string | null;
  class_name: string | null;
  confidence: number;
}

export interface RecentEventsResponse {
  events: CountEvent[];
  total_shown: number;
}

export interface HourlyCount {
  hour_start_ts: number;
  total: number;
  by_direction: Record<string, number>;
  by_class: Record<string, number>;
}

export interface HourlyStatsResponse {
  hours: HourlyCount[];
  start_ts: number;
  end_ts: number;
}

export interface DailyCount {
  date: string;
  day_start_ts: number;
  total: number;
  by_direction: Record<string, number>;
  by_class: Record<string, number>;
}

export interface DailyStatsResponse {
  days: DailyCount[];
  start_ts: number;
  end_ts: number;
}

export interface PipelineStageStatus {
  name: string;
  status: "running" | "degraded" | "offline";
  message: string | null;
}

export interface PipelineStatusResponse {
  stages: PipelineStageStatus[];
  overall_status: "running" | "degraded" | "offline";
}

export interface StatsSummary {
  total_detections: number;
  last_hour: number;
  last_24h: number;
  last_24h_by_direction: Record<string, number>;
}

export interface HealthResponse {
  timestamp?: number;
  platform?: string;
  python?: string;
  cwd?: string;
  storage_db_path?: string;
  log_path?: string;
  [key: string]: unknown;
}

export interface CountingConfig {
  mode?: "line" | "gate";
  line_a?: number[][];
  line_b?: number[][];
  direction_labels?: {
    positive?: string;
    negative?: string;
    a_to_b?: string;
    b_to_a?: string;
  };
  min_age_frames?: number;
  min_displacement_px?: number;
  max_gap_frames?: number;
}

export interface CalibrationResponse {
  counting?: CountingConfig;
  camera?: Record<string, unknown>;
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

// Status endpoints
export const fetchStatus = () => json<StatusResponse>("/api/status");
export const fetchCompactStatus = () => json<CompactStatusResponse>("/api/status/compact");

// Stats and health
export const fetchStats = () => json<StatsSummary>("/api/stats/summary");
export const fetchHealth = () => json<HealthResponse>("/api/health");

// Config
export const fetchConfig = () => json<Record<string, unknown>>("/api/config");
export const saveConfig = (overrides: Record<string, unknown>) =>
  json<{ ok: boolean }>("/api/config", {
    method: "POST",
    body: JSON.stringify({ overrides }),
  });

// Calibration (counting config)
export const fetchCalibration = () => json<CalibrationResponse>("/api/calibration");
export const saveCalibration = (payload: Partial<CalibrationResponse>) =>
  json<{ ok: boolean }>("/api/calibration", {
    method: "POST",
    body: JSON.stringify(payload),
  });

// New Phase 2 endpoints
export const fetchRecentEvents = (limit: number = 50) =>
  json<RecentEventsResponse>(`/api/stats/recent?limit=${limit}`);

export const fetchHourlyStats = (days: number = 7) =>
  json<HourlyStatsResponse>(`/api/stats/hourly?days=${days}`);

export const fetchDailyStats = (days: number = 30) =>
  json<DailyStatsResponse>(`/api/stats/daily?days=${days}`);

export const fetchPipelineStatus = () =>
  json<PipelineStatusResponse>("/api/status/pipeline");
