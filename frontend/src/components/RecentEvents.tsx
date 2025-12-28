import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

export function RecentEvents({ events }: { events: string[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent events</CardTitle>
      </CardHeader>
      <CardContent className="space-y-1 text-sm">
        {events && events.length ? (
          events.map((e, i) => (
            <div key={`${e}-${i}`} className="rounded bg-slate-800/60 px-3 py-2">
              {e}
            </div>
          ))
        ) : (
          <div className="text-slate-400">No recent events</div>
        )}
      </CardContent>
    </Card>
  );
}

