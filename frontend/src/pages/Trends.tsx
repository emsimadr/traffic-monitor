import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchHourlyStats, fetchDailyStats } from "../lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { TimeRangePicker } from "../components/TimeRangePicker";
import { HourlyChart } from "../components/HourlyChart";
import { DailyChart } from "../components/DailyChart";
import {
  TabsRoot,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../components/ui/tabs";

export default function Trends() {
  const [startDate, setStartDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 7);
    return d;
  });
  const [endDate, setEndDate] = useState(new Date());
  const [classFilter, setClassFilter] = useState<Set<string>>(new Set());

  const handleRangeChange = (start: Date, end: Date) => {
    setStartDate(start);
    setEndDate(end);
  };

  const days = Math.ceil((endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24));

  // Fetch data based on range (prefer daily for >30 days)
  const useDaily = days > 30;

  const hourlyQuery = useQuery({
    queryKey: ["hourly-stats", days],
    queryFn: () => fetchHourlyStats(days),
    enabled: !useDaily,
  });

  const dailyQuery = useQuery({
    queryKey: ["daily-stats", days],
    queryFn: () => fetchDailyStats(days),
    enabled: useDaily,
  });

  const data = useDaily ? dailyQuery.data : hourlyQuery.data;
  const isLoading = useDaily ? dailyQuery.isLoading : hourlyQuery.isLoading;

  // Extract all unique classes from data
  const allClasses = useMemo(() => {
    if (!data) return [];
    const classSet = new Set<string>();
    const items = "hours" in data ? data.hours : data.days;
    for (const item of items) {
      for (const className of Object.keys(item.by_class)) {
        classSet.add(className);
      }
    }
    return Array.from(classSet).sort();
  }, [data]);

  const toggleClass = (className: string) => {
    setClassFilter((prev) => {
      const next = new Set(prev);
      if (next.has(className)) {
        next.delete(className);
      } else {
        next.add(className);
      }
      return next;
    });
  };

  const handleExport = () => {
    const startTs = Math.floor(startDate.getTime() / 1000);
    const endTs = Math.floor(endDate.getTime() / 1000);
    const url = `/api/stats/export?start_ts=${startTs}&end_ts=${endTs}&format=csv`;
    window.open(url, "_blank");
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Trends</h1>
        <Button onClick={handleExport} variant="outline">
          Export CSV
        </Button>
      </div>

      {/* Time range picker */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Time Range</CardTitle>
        </CardHeader>
        <CardContent>
          <TimeRangePicker onRangeChange={handleRangeChange} />
        </CardContent>
      </Card>

      {/* Class filters */}
      {allClasses.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Class Filter</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {allClasses.map((className) => (
                <ClassFilterButton
                  key={className}
                  className={className}
                  active={classFilter.size === 0 || classFilter.has(className)}
                  onClick={() => toggleClass(className)}
                />
              ))}
              {classFilter.size > 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setClassFilter(new Set())}
                >
                  Clear Filter
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Charts */}
      <TabsRoot defaultValue="chart" className="space-y-4">
        <TabsList>
          <TabsTrigger value="chart">Chart</TabsTrigger>
          <TabsTrigger value="breakdown">Breakdown</TabsTrigger>
        </TabsList>

        <TabsContent value="chart">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">
                {useDaily ? "Daily Counts" : "Hourly Counts"}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading && (
                <div className="flex h-64 items-center justify-center text-slate-500">
                  Loading...
                </div>
              )}
              {!isLoading && data && (
                <>
                  {useDaily && "days" in data && (
                    <DailyChart data={data.days} classFilter={classFilter} />
                  )}
                  {!useDaily && "hours" in data && (
                    <HourlyChart data={data.hours} classFilter={classFilter} />
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="breakdown">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Class Breakdown</CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading && (
                <div className="text-slate-500">Loading...</div>
              )}
              {!isLoading && data && (
                <ClassBreakdownTable
                  data={data}
                  classFilter={classFilter}
                  useDaily={useDaily}
                />
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </TabsRoot>
    </div>
  );
}

function ClassFilterButton({
  className,
  active,
  onClick,
}: {
  className: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <Button
      variant={active ? "default" : "outline"}
      size="sm"
      onClick={onClick}
    >
      {className}
    </Button>
  );
}

function ClassBreakdownTable({
  data,
  classFilter,
  useDaily,
}: {
  data: any;
  classFilter: Set<string>;
  useDaily: boolean;
}) {
  const items = useDaily ? data.days : data.hours;

  // Aggregate totals by class
  const totals: Record<string, number> = {};
  for (const item of items) {
    for (const [className, count] of Object.entries(item.by_class)) {
      if (classFilter.size === 0 || classFilter.has(className as string)) {
        totals[className as string] = (totals[className as string] || 0) + (count as number);
      }
    }
  }

  const entries = Object.entries(totals).sort((a, b) => b[1] - a[1]);

  if (entries.length === 0) {
    return <div className="text-slate-500">No data available</div>;
  }

  return (
    <div className="space-y-2">
      {entries.map(([className, count]) => (
        <div
          key={className}
          className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900/50 p-3"
        >
          <span className="font-medium">{className}</span>
          <span className="text-slate-400">{count.toLocaleString()}</span>
        </div>
      ))}
    </div>
  );
}

