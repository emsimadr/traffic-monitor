import { useEffect, useRef, useState } from "react";
import { Button } from "../ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { Label } from "../ui/label";
import { Input } from "../ui/input";

type Point = { x: number; y: number };
type Line = [Point, Point] | null;

type Props = {
  lineA: Line;
  lineB: Line;
  directionLabels: { a_to_b: string; b_to_a: string };
  onChange: (lineA: Line, lineB: Line, directionLabels: { a_to_b: string; b_to_a: string }) => void;
};

export function CountingGateEditor({ lineA, lineB, directionLabels, onChange }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);

  const [localLineA, setLocalLineA] = useState<Line>(lineA);
  const [localLineB, setLocalLineB] = useState<Line>(lineB);
  const [labels, setLabels] = useState(directionLabels);
  const [activeGate, setActiveGate] = useState<"A" | "B">("A");
  const [tempPoint, setTempPoint] = useState<Point | null>(null);

  useEffect(() => setLocalLineA(lineA), [lineA]);
  useEffect(() => setLocalLineB(lineB), [lineB]);
  useEffect(() => setLabels(directionLabels), [directionLabels]);

  useEffect(() => {
    draw();
  }, [localLineA, localLineB, tempPoint, activeGate]);

  const toPoint = (ev: React.MouseEvent<HTMLCanvasElement, MouseEvent>): Point => {
    const rect = ev.currentTarget.getBoundingClientRect();
    return {
      x: (ev.clientX - rect.left) / rect.width,
      y: (ev.clientY - rect.top) / rect.height,
    };
  };

  const handleClick = (ev: React.MouseEvent<HTMLCanvasElement, MouseEvent>) => {
    const p = toPoint(ev);

    if (activeGate === "A") {
      if (!tempPoint) {
        setTempPoint(p);
      } else {
        setLocalLineA([tempPoint, p]);
        setTempPoint(null);
      }
    } else {
      if (!tempPoint) {
        setTempPoint(p);
      } else {
        setLocalLineB([tempPoint, p]);
        setTempPoint(null);
      }
    }
  };

  const draw = () => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img) return;
    canvas.width = img.clientWidth;
    canvas.height = img.clientHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const drawLine = (line: Line, color: string) => {
      if (!line) return;
      const [p1, p2] = line;
      ctx.strokeStyle = color;
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(p1.x * canvas.width, p1.y * canvas.height);
      ctx.lineTo(p2.x * canvas.width, p2.y * canvas.height);
      ctx.stroke();

      // Draw endpoints
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(p1.x * canvas.width, p1.y * canvas.height, 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.beginPath();
      ctx.arc(p2.x * canvas.width, p2.y * canvas.height, 5, 0, Math.PI * 2);
      ctx.fill();
    };

    // Draw Gate A (cyan)
    drawLine(localLineA, "rgba(0, 201, 255, 0.9)");

    // Draw Gate B (coral)
    drawLine(localLineB, "rgba(255, 99, 71, 0.9)");

    // Draw temp point
    if (tempPoint) {
      const color = activeGate === "A" ? "rgba(0, 201, 255, 0.7)" : "rgba(255, 99, 71, 0.7)";
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(tempPoint.x * canvas.width, tempPoint.y * canvas.height, 6, 0, Math.PI * 2);
      ctx.fill();
    }
  };

  const save = () => {
    onChange(localLineA, localLineB, labels);
  };

  const reset = () => {
    setLocalLineA(null);
    setLocalLineB(null);
    setTempPoint(null);
  };

  const getStatus = () => {
    const aStatus = localLineA ? "✓" : tempPoint && activeGate === "A" ? "P1 set" : "—";
    const bStatus = localLineB ? "✓" : tempPoint && activeGate === "B" ? "P1 set" : "—";
    return { a: aStatus, b: bStatus };
  };

  const status = getStatus();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Counting Gate</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex gap-2 mb-2">
          <Button
            type="button"
            variant={activeGate === "A" ? "default" : "outline"}
            onClick={() => {
              setActiveGate("A");
              setTempPoint(null);
            }}
            className={activeGate === "A" ? "bg-cyan-600 hover:bg-cyan-700" : ""}
          >
            Gate A [{status.a}]
          </Button>
          <Button
            type="button"
            variant={activeGate === "B" ? "default" : "outline"}
            onClick={() => {
              setActiveGate("B");
              setTempPoint(null);
            }}
            className={activeGate === "B" ? "bg-orange-600 hover:bg-orange-700" : ""}
          >
            Gate B [{status.b}]
          </Button>
        </div>

        <div className="relative overflow-hidden rounded-xl border border-slate-800">
          <img
            ref={imgRef}
            src="/api/camera/snapshot.jpg"
            alt="Snapshot"
            className="w-full"
            onLoad={draw}
          />
          <canvas
            ref={canvasRef}
            className="absolute left-0 top-0 h-full w-full cursor-crosshair"
            onClick={handleClick}
          />
        </div>

        <p className="text-sm text-slate-400">
          Click two points to define each gate line. Gate A (cyan) and Gate B (coral) form a counting zone.
        </p>

        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <Label>A → B direction</Label>
            <Input
              value={labels.a_to_b}
              onChange={(e) => setLabels({ ...labels, a_to_b: e.target.value })}
              placeholder="northbound"
            />
          </div>
          <div>
            <Label>B → A direction</Label>
            <Input
              value={labels.b_to_a}
              onChange={(e) => setLabels({ ...labels, b_to_a: e.target.value })}
              placeholder="southbound"
            />
          </div>
        </div>

        <div className="flex gap-2">
          <Button type="button" onClick={reset} variant="outline">
            Reset
          </Button>
          <Button type="button" onClick={save}>
            Save Gate
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

