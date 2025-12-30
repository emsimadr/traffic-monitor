import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchCalibration, fetchConfig, saveCalibration, saveConfig, CalibrationResponse } from "../lib/api";
import { Tabs } from "../components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Button } from "../components/ui/button";
import { CountingGateEditor } from "../components/Config/CountingGateEditor";
import { CountingLineEditor } from "../components/Config/CountingLineEditor";
import { Switch } from "../components/ui/switch";

type Point = { x: number; y: number };
type Line = [Point, Point] | null;

type TabId = "camera" | "counting" | "detection" | "advanced";

export default function Configure() {
  const [active, setActive] = useState<TabId>("counting");
  const queryClient = useQueryClient();

  const cfgQuery = useQuery({ queryKey: ["config"], queryFn: fetchConfig });
  const calQuery = useQuery({ queryKey: ["calibration"], queryFn: fetchCalibration });

  const saveCfg = useMutation({
    mutationFn: (overrides: Record<string, unknown>) => saveConfig(overrides),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["config"] }),
  });

  const saveCal = useMutation({
    mutationFn: (payload: Partial<CalibrationResponse>) => saveCalibration(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["calibration"] }),
  });

  const overrides = cfgQuery.data ?? {};

  // Parse counting config from calibration data
  // Gate counting is the default for bi-directional streets
  const countingConfig = useMemo(() => {
    const counting = calQuery.data?.counting || {};
    const mode = counting.mode || "gate";  // Gate is the default
    const la = counting.line_a;
    const lb = counting.line_b;
    // All modes use a_to_b/b_to_a direction codes for DB/API consistency
    const labels = counting.direction_labels || {
      a_to_b: "northbound",
      b_to_a: "southbound",
    };

    const parseLine = (l: number[][] | undefined): Line => {
      if (Array.isArray(l) && l.length === 2) {
        return [{ x: l[0][0], y: l[0][1] }, { x: l[1][0], y: l[1][1] }];
      }
      return null;
    };

    return {
      mode,
      lineA: parseLine(la),
      lineB: parseLine(lb),
      directionLabels: labels,
      minAgeFrames: counting.min_age_frames ?? 3,
      minDisplacementPx: counting.min_displacement_px ?? 15,
      maxGapFrames: counting.max_gap_frames ?? 30,
    };
  }, [calQuery.data]);

  const tabs = [
    { id: "counting", label: "Counting" },
    { id: "camera", label: "Camera" },
    { id: "detection", label: "Detection" },
    { id: "advanced", label: "Advanced" },
  ];

  return (
    <div className="space-y-4">
      <Tabs tabs={tabs} active={active} onChange={(t) => setActive(t as TabId)}>
        {active === "counting" && (
          <CountingTab
            config={countingConfig}
            onSave={(payload) => saveCal.mutate(payload)}
            saving={saveCal.isPending}
          />
        )}
        {active === "camera" && (
          <CameraTab overrides={overrides} onSave={(o) => saveCfg.mutate(o)} saving={saveCfg.isPending} />
        )}
        {active === "detection" && (
          <DetectionTab overrides={overrides} onSave={(o) => saveCfg.mutate(o)} saving={saveCfg.isPending} />
        )}
        {active === "advanced" && <AdvancedTab cfg={cfgQuery.data} />}
      </Tabs>
    </div>
  );
}

type CountingConfigState = {
  mode: string;
  lineA: Line;
  lineB: Line;
  // All modes use a_to_b/b_to_a direction codes for DB/API consistency
  directionLabels: {
    a_to_b?: string;
    b_to_a?: string;
  };
  minAgeFrames: number;
  minDisplacementPx: number;
  maxGapFrames: number;
};

function CountingTab({
  config,
  onSave,
  saving,
}: {
  config: CountingConfigState;
  onSave: (payload: Partial<CalibrationResponse>) => void;
  saving: boolean;
}) {
  const [mode, setMode] = useState(config.mode);

  useEffect(() => {
    setMode(config.mode);
  }, [config.mode]);

  const handleModeChange = (newMode: string) => {
    setMode(newMode);
    onSave({
      counting: {
        mode: newMode as "line" | "gate",
      },
    });
  };

  const toArray = (line: Line) =>
    line ? [[line[0].x, line[0].y], [line[1].x, line[1].y]] : undefined;

  const handleGateSave = (
    newLineA: Line,
    newLineB: Line,
    newLabels: { a_to_b: string; b_to_a: string }
  ) => {
    onSave({
      counting: {
        mode: "gate",
        line_a: toArray(newLineA),
        line_b: toArray(newLineB),
        direction_labels: {
          ...config.directionLabels,
          ...newLabels,
        },
      },
    });
  };

  const handleLineSave = (
    line: Line,
    labels: { a_to_b: string; b_to_a: string }
  ) => {
    onSave({
      counting: {
        mode: "line",
        line_a: toArray(line), // Store single line as line_a
        direction_labels: labels,
      },
    });
  };

  return (
    <div className="space-y-4">
      {/* Mode selector */}
      <Card>
        <CardHeader>
          <CardTitle>Counting Mode</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Button
              variant={mode === "line" ? "default" : "outline"}
              onClick={() => handleModeChange("line")}
              disabled={saving}
            >
              Single Line
            </Button>
            <Button
              variant={mode === "gate" ? "default" : "outline"}
              onClick={() => handleModeChange("gate")}
              disabled={saving}
            >
              Two-Line Gate
            </Button>
          </div>
          <p className="mt-2 text-sm text-slate-400">
            {mode === "line"
              ? "Count when tracks cross a single line. Simple setup for basic counting."
              : "Count when tracks cross Line A then Line B (or vice versa). More accurate for directional counting."}
          </p>
        </CardContent>
      </Card>

      {/* Mode-specific editor */}
      {mode === "gate" ? (
        <CountingGateEditor
          lineA={config.lineA}
          lineB={config.lineB}
          directionLabels={{
            a_to_b: config.directionLabels.a_to_b || "northbound",
            b_to_a: config.directionLabels.b_to_a || "southbound",
          }}
          onChange={handleGateSave}
        />
      ) : (
        <CountingLineEditor
          line={config.lineA}
          directionLabels={{
            a_to_b: config.directionLabels.a_to_b || "northbound",
            b_to_a: config.directionLabels.b_to_a || "southbound",
          }}
          onChange={handleLineSave}
        />
      )}

      {/* Advanced counting settings */}
      <CountingAdvancedSettings
        minAgeFrames={config.minAgeFrames}
        minDisplacementPx={config.minDisplacementPx}
        maxGapFrames={config.maxGapFrames}
        mode={mode}
        onSave={(settings) => onSave({ counting: settings })}
        saving={saving}
      />
    </div>
  );
}

function CountingAdvancedSettings({
  minAgeFrames,
  minDisplacementPx,
  maxGapFrames,
  mode,
  onSave,
  saving,
}: {
  minAgeFrames: number;
  minDisplacementPx: number;
  maxGapFrames: number;
  mode: string;
  onSave: (settings: Record<string, number>) => void;
  saving: boolean;
}) {
  const [localMinAge, setLocalMinAge] = useState(minAgeFrames);
  const [localMinDisp, setLocalMinDisp] = useState(minDisplacementPx);
  const [localMaxGap, setLocalMaxGap] = useState(maxGapFrames);

  useEffect(() => {
    setLocalMinAge(minAgeFrames);
    setLocalMinDisp(minDisplacementPx);
    setLocalMaxGap(maxGapFrames);
  }, [minAgeFrames, minDisplacementPx, maxGapFrames]);

  const save = () => {
    onSave({
      min_age_frames: localMinAge,
      min_displacement_px: localMinDisp,
      max_gap_frames: localMaxGap,
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Counting Constraints</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-3 gap-3">
          <div>
            <Label>Min Age (frames)</Label>
            <Input
              type="number"
              value={localMinAge}
              onChange={(e) => setLocalMinAge(Number(e.target.value))}
            />
            <p className="text-xs text-slate-500 mt-1">Track must exist this many frames</p>
          </div>
          <div>
            <Label>Min Displacement (px)</Label>
            <Input
              type="number"
              value={localMinDisp}
              onChange={(e) => setLocalMinDisp(Number(e.target.value))}
            />
            <p className="text-xs text-slate-500 mt-1">Track must move this far</p>
          </div>
          {mode === "gate" && (
            <div>
              <Label>Max Gap (frames)</Label>
              <Input
                type="number"
                value={localMaxGap}
                onChange={(e) => setLocalMaxGap(Number(e.target.value))}
              />
              <p className="text-xs text-slate-500 mt-1">Max frames between line crossings</p>
            </div>
          )}
        </div>
        <Button onClick={save} disabled={saving}>
          {saving ? "Saving..." : "Save Constraints"}
        </Button>
      </CardContent>
    </Card>
  );
}

function CameraTab({
  overrides,
  onSave,
  saving,
}: {
  overrides: Record<string, unknown>;
  onSave: (o: Record<string, unknown>) => void;
  saving: boolean;
}) {
  const camera = (overrides?.camera as Record<string, unknown>) || {};
  const [deviceId, setDeviceId] = useState(String(camera?.device_id ?? ""));
  const [fps, setFps] = useState(Number(camera?.fps) || 30);
  const [rotate, setRotate] = useState(Number(camera?.rotate) || 0);
  const [swap, setSwap] = useState(!!camera?.swap_rb);

  useEffect(() => {
    const cam = (overrides?.camera as Record<string, unknown>) || {};
    setDeviceId(String(cam?.device_id ?? ""));
    setFps(Number(cam?.fps) || 30);
    setRotate(Number(cam?.rotate) || 0);
    setSwap(!!cam?.swap_rb);
  }, [overrides]);

  const save = () =>
    onSave({
      ...overrides,
      camera: {
        ...camera,
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
            <Label>Rotate (0, 90, 180, 270)</Label>
            <Input type="number" value={rotate} onChange={(e) => setRotate(Number(e.target.value))} />
          </div>
          <div className="flex items-end">
            <Switch checked={swap} onChange={setSwap} label="Swap R/B" />
          </div>
        </div>
        <Button onClick={save} disabled={saving}>
          {saving ? "Saving..." : "Save Camera"}
        </Button>
        <p className="text-xs text-slate-500">
          Note: Camera changes require a restart to take effect.
        </p>
      </CardContent>
    </Card>
  );
}

function DetectionTab({
  overrides,
  onSave,
  saving,
}: {
  overrides: Record<string, unknown>;
  onSave: (o: Record<string, unknown>) => void;
  saving: boolean;
}) {
  const detection = (overrides?.detection as Record<string, unknown>) || {};
  const tracking = (overrides?.tracking as Record<string, unknown>) || {};

  const [minArea, setMinArea] = useState(Number(detection?.min_contour_area) || 1000);
  const [iou, setIou] = useState(Number(tracking?.iou_threshold) || 0.3);

  useEffect(() => {
    const det = (overrides?.detection as Record<string, unknown>) || {};
    const trk = (overrides?.tracking as Record<string, unknown>) || {};
    setMinArea(Number(det?.min_contour_area) || 1000);
    setIou(Number(trk?.iou_threshold) || 0.3);
  }, [overrides]);

  const save = () =>
    onSave({
      ...overrides,
      detection: { ...detection, min_contour_area: Number(minArea) || 0 },
      tracking: { ...tracking, iou_threshold: Number(iou) || 0.3 },
    });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Detection & Tracking</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label>Min Contour Area</Label>
            <Input type="number" value={minArea} onChange={(e) => setMinArea(Number(e.target.value))} />
          </div>
          <div>
            <Label>Tracking IoU Threshold</Label>
            <Input type="number" step="0.01" value={iou} onChange={(e) => setIou(Number(e.target.value))} />
          </div>
        </div>
        <Button onClick={save} disabled={saving}>
          {saving ? "Saving..." : "Save Detection"}
        </Button>
      </CardContent>
    </Card>
  );
}

function AdvancedTab({ cfg }: { cfg: Record<string, unknown> | undefined }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Advanced (Read-Only)</CardTitle>
      </CardHeader>
      <CardContent>
        <Textarea value={JSON.stringify(cfg ?? {}, null, 2)} readOnly rows={20} className="font-mono text-xs" />
      </CardContent>
    </Card>
  );
}
