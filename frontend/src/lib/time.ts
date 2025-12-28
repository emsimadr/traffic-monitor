export function formatDistanceToNowStrict(secondsAgo: number) {
  if (secondsAgo == null) return "—";
  if (secondsAgo < 1) return "<1s ago";
  if (secondsAgo < 60) return `${Math.round(secondsAgo)}s ago`;
  const minutes = Math.floor(secondsAgo / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

