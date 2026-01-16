/**
 * Format timestamp (ms) as relative time (e.g., "2m ago", "5s ago")
 */
export function formatDistanceToNow(timestampMs: number): string {
  const now = Date.now();
  const diffMs = now - timestampMs;
  const diffSec = Math.floor(diffMs / 1000);
  
  if (diffSec < 60) {
    return `${diffSec}s`;
  } else if (diffSec < 3600) {
    return `${Math.floor(diffSec / 60)}m`;
  } else if (diffSec < 86400) {
    return `${Math.floor(diffSec / 3600)}h`;
  } else {
    return `${Math.floor(diffSec / 86400)}d`;
  }
}

/**
 * Format Unix timestamp (seconds) as local date/time string
 */
export function formatDateTime(timestampSec: number): string {
  return new Date(timestampSec * 1000).toLocaleString();
}

/**
 * Format Unix timestamp (seconds) as local date string
 */
export function formatDate(timestampSec: number): string {
  return new Date(timestampSec * 1000).toLocaleDateString();
}
