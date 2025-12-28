import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";

async function fetchLogs() {
  const res = await fetch("/api/logs/tail?lines=200");
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

export default function Logs() {
  const query = useQuery({ queryKey: ["logs"], queryFn: fetchLogs, refetchOnWindowFocus: false });

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <CardTitle>Logs (tail)</CardTitle>
        <Button variant="outline" onClick={() => query.refetch()} disabled={query.isLoading}>
          Refresh
        </Button>
      </CardHeader>
      <CardContent>
        <pre className="max-h-[70vh] overflow-auto whitespace-pre-wrap text-xs text-slate-200">
          {(query.data?.lines || []).join("")}
        </pre>
      </CardContent>
    </Card>
  );
}

