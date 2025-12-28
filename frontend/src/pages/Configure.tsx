import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchCalibration, fetchConfig, saveCalibration, saveConfig } from "../lib/api";
import { Tabs } from "../components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Button } from "../components/ui/button";
import { CountingGateEditor } from "../components/Config/CountingGateEditor";
import { Switch } from "../components/ui/switch";

type Point = { x: number; y: number };
type Line = [Point, Point] | null;

type TabId = "camera" | "roi" | "gate" | "detection" | "schedule" | "advanced";

export default function Configure() {
  const [active, setActive] = useState<TabId>("camera");
  const queryClient = useQueryClient();

  const cfgQuery = useQuery({ queryKey: ["config"], queryFn: fetchConfig });
  const calQuery = useQuery({ queryKey: ["calibration"], queryFn: fetchCalibration });

  const saveCfg = useMutation({
    mutationFn: (overrides: any) => saveConfig(overrides),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["config"] }),
  });

  const saveCal = useMutation({
    mutationFn: (payload: any) => saveCalibration(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["calibration"] }),
  });

  const overrides = cfgQuery.data ?? {};

  // Parse gate lines from calibration data
  const { lineA, lineB, directionLabels } = useMemo(() => {
    const counting = calQuery.data?.counting || {};
    const la = counting.line_a;
    const lb = counting.line_b;
    const labels = counting.direction_labels || { a_to_b: "northbound", b_to_a: "southbound" };

    const parseLine = (l: number[][] | null): Line => {
      if (Array.isArray(l) && l.length === 2) {
        return [{ x: l[0][0], y: l[0][1] }, { x: l[1][0], y: l[1][1] }];
      }
      return null;
    };

    return {
      lineA: parseLine(la),
      lineB: parseLine(lb),
      directionLabels: labels,
    };
  }, [calQuery.data]);

  const tabs = [
    { id: "camera", label: "Camera" },
    { id: "roi", label: "ROI" },
    { id: "gate", label: "Counting Gate" },
    { id: "detection", label: "Detection" },
    { id: "schedule", label: "Schedule" },
    { id: "advanced", label: "Advanced" },
  ];

  return (
    <div className="space-y-4">
      <Tabs tabs={tabs} active={active} onChange={(t) => setActive(t as TabId)}>
        {active === "camera" && (
          <CameraTab overrides={overrides} onSave={(o) => saveCfg.mutate(o)} saving={saveCfg.isPending} />
        )}
        {active === "roi" && (
          <PlaceholderCard title="ROI" note="ROI selection not yet implemented (v1 placeholder)." />
        )}
        {active === "gate" && (
          <CountingGateEditor
            lineA={lineA}
            lineB={lineB}
            directionLabels={directionLabels}
            onChange={(newLineA, newLineB, newLabels) => {
              const toArray = (line: Line) =>
                line ? [[line[0].x, line[0].y], [line[1].x, line[1].y]] : null;
              saveCal.mutate({
                counting: {
                  line_a: toArray(newLineA),
                  line_b: toArray(newLineB),
                  direction_labels: newLabels,
                },
              });
            }}
          />
        )}
        {active === "detection" && (
          <DetectionTab overrides={overrides} onSave={(o) => saveCfg.mutate(o)} saving={saveCfg.isPending} />
        )}
        {active === "schedule" && (
          <PlaceholderCard title="Schedule" note="Weekly schedule placeholder for v1." />
        )}
        {active === "advanced" && <AdvancedTab cfg={cfgQuery.data} />}
      </Tabs>
    </div>
  );
}

function CameraTab({
  overrides,
  onSave,
  saving,
}: {
  overrides: any;
  onSave: (o: any) => void;
  saving: boolean;
}) {
  const [deviceId, setDeviceId] = useState(overrides?.camera?.device_id ?? "");
  const [fps, setFps] = useState(overrides?.camera?.fps ?? 30);
  const [rotate, setRotate] = useState(overrides?.camera?.rotate ?? 0);
  const [swap, setSwap] = useState(!!overrides?.camera?.swap_rb);

  useEffect(() => {
    setDeviceId(overrides?.camera?.device_id ?? "");
    setFps(overrides?.camera?.fps ?? 30);
    setRotate(overrides?.camera?.rotate ?? 0);
    setSwap(!!overrides?.camera?.swap_rb);
  }, [overrides]);

  const save = () =>
    onSave({
      ...overrides,
      camera: {
        ...(overrides?.camera || {}),
        device_id: deviceId,
        fps: Number(fps) || 0,
        rotate: Number(rotate) || 0,
        swap_rb: swap,
      },
    });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Camera</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label>Device ID / URL</Label>
            <Input value={deviceId} onChange={(e) => setDeviceId(e.target.value)} />
          </div>
          <div>
            <Label>FPS</Label>
            <Input type="number" value={fps} onChange={(e) => setFps(Number(e.target.value))} />
          </div>
          <div>
            <Label>Rotate</Label>
            <Input type="number" value={rotate} onChange={(e) => setRotate(Number(e.target.value))} />
          </div>
          <div className="flex items-end">
            <Switch checked={swap} onChange={setSwap} label="Swap R/B" />
          </div>
        </div>
        <Button onClick={save} disabled={saving}>
          {saving ? "Saving..." : "Save camera"}
        </Button>
      </CardContent>
    </Card>
  );
}

function DetectionTab({
  overrides,
  onSave,
  saving,
}: {
  overrides: any;
  onSave: (o: any) => void;
  saving: boolean;
}) {
  const [minArea, setMinArea] = useState(overrides?.detection?.min_contour_area ?? 1000);
  const [iou, setIou] = useState(overrides?.tracking?.iou_threshold ?? 0.3);

  useEffect(() => {
    setMinArea(overrides?.detection?.min_contour_area ?? 1000);
    setIou(overrides?.tracking?.iou_threshold ?? 0.3);
  }, [overrides]);

  const save = () =>
    onSave({
      ...overrides,
      detection: { ...(overrides?.detection || {}), min_contour_area: Number(minArea) || 0 },
      tracking: { ...(overrides?.tracking || {}), iou_threshold: Number(iou) || 0.3 },
    });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Detection & Tracking</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label>Min contour area</Label>
            <Input type="number" value={minArea} onChange={(e) => setMinArea(Number(e.target.value))} />
          </div>
          <div>
            <Label>Tracking IoU threshold</Label>
            <Input type="number" step="0.01" value={iou} onChange={(e) => setIou(Number(e.target.value))} />
          </div>
        </div>
        <Button onClick={save} disabled={saving}>
          {saving ? "Saving..." : "Save detection"}
        </Button>
      </CardContent>
    </Card>
  );
}

function AdvancedTab({ cfg }: { cfg: any }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Advanced (read-only)</CardTitle>
      </CardHeader>
      <CardContent>
        <Textarea value={JSON.stringify(cfg ?? {}, null, 2)} readOnly rows={16} />
      </CardContent>
    </Card>
  );
}

function PlaceholderCard({ title, note }: { title: string; note: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="text-sm text-slate-300">{note}</CardContent>
    </Card>
  );
}
