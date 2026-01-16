import { useQuery } from "@tanstack/react-query";
import { fetchRecentEvents } from "../lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { formatDistanceToNow } from "../lib/time";

export function RecentEventsTable() {
  const { data, isLoading } = useQuery({
    queryKey: ["recent-events"],
    queryFn: () => fetchRecentEvents(10),
    refetchInterval: 5000, // Refresh every 5s
  });

  const events = data?.events ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Recent Events</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && (
          <div className="text-sm text-slate-500">Loading...</div>
        )}
        {!isLoading && events.length === 0 && (
          <div className="text-sm text-slate-500">No events yet</div>
        )}
        {!isLoading && events.length > 0 && (
          <div className="space-y-2">
            {events.map((event, idx) => (
              <EventRow key={`${event.ts}-${idx}`} event={event} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function EventRow({ event }: { event: { ts: number; direction_label: string | null; direction_code: string; class_name: string | null; confidence: number } }) {
  const timeAgo = formatDistanceToNow(event.ts);
  const direction = event.direction_label || event.direction_code;
  const className = event.class_name || "unclassified";
  
  // Color code by class
  const classColor = getClassColor(className);
  
  return (
    <div className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900/50 p-2 text-sm">
      <div className="flex items-center gap-3">
        <div className="text-xs text-slate-500 w-16">{timeAgo}</div>
        <div className="flex items-center gap-2">
          <span className={`inline-block h-2 w-2 rounded-full ${classColor}`} />
          <span className="font-medium">{className}</span>
        </div>
        <div className="text-slate-400">→ {direction}</div>
      </div>
      <div className="text-xs text-slate-500">
        {(event.confidence * 100).toFixed(0)}%
      </div>
    </div>
  );
}

function getClassColor(className: string): string {
  const colors: Record<string, string> = {
    car: "bg-blue-400",
    truck: "bg-blue-500",
    bus: "bg-blue-600",
    bicycle: "bg-green-400",
    motorcycle: "bg-green-500",
    person: "bg-amber-400",
    pedestrian: "bg-amber-400",
    unclassified: "bg-slate-500",
  };
  return colors[className.toLowerCase()] || "bg-slate-400";
}

