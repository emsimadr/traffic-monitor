import { useEffect, useRef, useState } from "react";
import { Button } from "../ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { Label } from "../ui/label";
import { Input } from "../ui/input";

type Point = { x: number; y: number };
type Line = [Point, Point] | null;

type Props = {
  line: Line;
  // All modes use a_to_b/b_to_a direction codes for DB/API consistency
  directionLabels: { a_to_b: string; b_to_a: string };
  onChange: (line: Line, labels: { a_to_b: string; b_to_a: string }) => void;
};

/**
 * Single-line counting editor (fallback when gate is not feasible).
 * 
 * Internally, crossing from + to - side maps to A_TO_B,
 * and crossing from - to + side maps to B_TO_A.
 */
export function CountingLineEditor({ line, directionLabels, onChange }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);

  const [localLine, setLocalLine] = useState<Line>(line);
  const [labels, setLabels] = useState(directionLabels);
  const [tempPoint, setTempPoint] = useState<Point | null>(null);

  useEffect(() => setLocalLine(line), [line]);
  useEffect(() => setLabels(directionLabels), [directionLabels]);

  useEffect(() => {
    draw();
  }, [localLine, tempPoint]);

  const toPoint = (ev: React.MouseEvent<HTMLCanvasElement, MouseEvent>): Point => {
    const rect = ev.currentTarget.getBoundingClientRect();
    return {
      x: (ev.clientX - rect.left) / rect.width,
      y: (ev.clientY - rect.top) / rect.height,
    };
  };

  const handleClick = (ev: React.MouseEvent<HTMLCanvasElement, MouseEvent>) => {
    const p = toPoint(ev);

    if (!tempPoint) {
      setTempPoint(p);
    } else {
      setLocalLine([tempPoint, p]);
      setTempPoint(null);
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

    // Draw the counting line (green)
    if (localLine) {
      const [p1, p2] = localLine;
      ctx.strokeStyle = "rgba(74, 222, 128, 0.9)"; // Green
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(p1.x * canvas.width, p1.y * canvas.height);
      ctx.lineTo(p2.x * canvas.width, p2.y * canvas.height);
      ctx.stroke();

      // Draw endpoints
      ctx.fillStyle = "rgba(74, 222, 128, 0.9)";
      ctx.beginPath();
      ctx.arc(p1.x * canvas.width, p1.y * canvas.height, 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.beginPath();
      ctx.arc(p2.x * canvas.width, p2.y * canvas.height, 5, 0, Math.PI * 2);
      ctx.fill();

      // Draw direction arrows showing A→B and B→A sides
      const midX = (p1.x + p2.x) / 2 * canvas.width;
      const midY = (p1.y + p2.y) / 2 * canvas.height;
      const dx = p2.x - p1.x;
      const dy = p2.y - p1.y;
      const perpX = -dy * 20;
      const perpY = dx * 20;

      // A→B direction (positive side)
      ctx.strokeStyle = "rgba(74, 222, 128, 0.7)";
      ctx.beginPath();
      ctx.moveTo(midX, midY);
      ctx.lineTo(midX + perpX, midY + perpY);
      ctx.stroke();
      ctx.fillStyle = "rgba(74, 222, 128, 0.9)";
      ctx.font = "12px sans-serif";
      ctx.fillText("A→B", midX + perpX - 12, midY + perpY + 4);

      // B→A direction (negative side)
      ctx.beginPath();
      ctx.moveTo(midX, midY);
      ctx.lineTo(midX - perpX, midY - perpY);
      ctx.stroke();
      ctx.fillText("B→A", midX - perpX - 12, midY - perpY + 4);
    }

    // Draw temp point
    if (tempPoint) {
      ctx.fillStyle = "rgba(74, 222, 128, 0.7)";
      ctx.beginPath();
      ctx.arc(tempPoint.x * canvas.width, tempPoint.y * canvas.height, 6, 0, Math.PI * 2);
      ctx.fill();
    }
  };

  const save = () => {
    onChange(localLine, labels);
  };

  const reset = () => {
    setLocalLine(null);
    setTempPoint(null);
  };

  const status = localLine ? "✓ Line set" : tempPoint ? "P1 set, click P2" : "Click to set P1";

  return (
    <Card>
      <CardHeader>
        <CardTitle>Counting Line (Fallback Mode)</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-slate-400">Status:</span>
          <span className={localLine ? "text-green-400" : "text-amber-400"}>{status}</span>
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
          Click two points to define the counting line. Direction is determined by which side the track crossed from.
          <br />
          <span className="font-medium">Note:</span> For bi-directional streets, Two-Line Gate mode is recommended.
        </p>

        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <Label>A → B Label</Label>
            <Input
              value={labels.a_to_b}
              onChange={(e) => setLabels({ ...labels, a_to_b: e.target.value })}
              placeholder="northbound"
            />
            <p className="text-xs text-slate-500 mt-1">Crossing from positive side</p>
          </div>
          <div>
            <Label>B → A Label</Label>
            <Input
              value={labels.b_to_a}
              onChange={(e) => setLabels({ ...labels, b_to_a: e.target.value })}
              placeholder="southbound"
            />
            <p className="text-xs text-slate-500 mt-1">Crossing from negative side</p>
          </div>
        </div>

        <div className="flex gap-2">
          <Button type="button" onClick={reset} variant="outline">
            Reset
          </Button>
          <Button type="button" onClick={save}>
            Save Line
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
