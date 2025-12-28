import { useEffect, useRef } from "react";

type Point = { x: number; y: number };

export function LiveFeed({ line }: { line: Point[] | null }) {
  const imgRef = useRef<HTMLImageElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const resize = () => {
    const img = imgRef.current;
    const canvas = canvasRef.current;
    if (!img || !canvas) return;
    canvas.width = img.clientWidth;
    canvas.height = img.clientHeight;
    draw();
  };

  const draw = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!line || line.length !== 2) return;
    ctx.strokeStyle = "rgba(56, 189, 248, 0.9)";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(line[0].x * canvas.width, line[0].y * canvas.height);
    ctx.lineTo(line[1].x * canvas.width, line[1].y * canvas.height);
    ctx.stroke();
  };

  useEffect(() => {
    draw();
  }, [line]);

  useEffect(() => {
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);

  return (
    <div className="relative overflow-hidden rounded-xl border border-slate-800 bg-slate-900">
      <img
        ref={imgRef}
        src="/api/camera/live.mjpg"
        alt="Live feed"
        className="h-full w-full object-contain"
        onLoad={resize}
      />
      <canvas ref={canvasRef} className="absolute inset-0 h-full w-full pointer-events-none" />
    </div>
  );
}

