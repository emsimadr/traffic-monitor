import { useState } from "react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";

type Preset = "7d" | "30d" | "90d" | "custom";

type Props = {
  onRangeChange: (start: Date, end: Date) => void;
};

export function TimeRangePicker({ onRangeChange }: Props) {
  const [preset, setPreset] = useState<Preset>("7d");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");

  const handlePreset = (p: Preset) => {
    setPreset(p);
    const end = new Date();
    let start: Date;

    switch (p) {
      case "7d":
        start = new Date(end.getTime() - 7 * 24 * 60 * 60 * 1000);
        break;
      case "30d":
        start = new Date(end.getTime() - 30 * 24 * 60 * 60 * 1000);
        break;
      case "90d":
        start = new Date(end.getTime() - 90 * 24 * 60 * 60 * 1000);
        break;
      default:
        return;
    }

    onRangeChange(start, end);
  };

  const handleCustom = () => {
    if (!customStart || !customEnd) return;
    const start = new Date(customStart);
    const end = new Date(customEnd);
    if (start >= end) return;
    setPreset("custom");
    onRangeChange(start, end);
  };

  return (
    <div className="flex flex-wrap items-end gap-4">
      {/* Preset buttons */}
      <div className="flex gap-2">
        <Button
          variant={preset === "7d" ? "default" : "outline"}
          size="sm"
          onClick={() => handlePreset("7d")}
        >
          Last 7 Days
        </Button>
        <Button
          variant={preset === "30d" ? "default" : "outline"}
          size="sm"
          onClick={() => handlePreset("30d")}
        >
          Last 30 Days
        </Button>
        <Button
          variant={preset === "90d" ? "default" : "outline"}
          size="sm"
          onClick={() => handlePreset("90d")}
        >
          Last 90 Days
        </Button>
      </div>

      {/* Custom range */}
      <div className="flex items-end gap-2">
        <div>
          <Label htmlFor="start" className="text-xs text-slate-400">
            Start
          </Label>
          <Input
            id="start"
            type="date"
            value={customStart}
            onChange={(e) => setCustomStart(e.target.value)}
            className="h-9"
          />
        </div>
        <div>
          <Label htmlFor="end" className="text-xs text-slate-400">
            End
          </Label>
          <Input
            id="end"
            type="date"
            value={customEnd}
            onChange={(e) => setCustomEnd(e.target.value)}
            className="h-9"
          />
        </div>
        <Button
          variant={preset === "custom" ? "default" : "outline"}
          size="sm"
          onClick={handleCustom}
          className="h-9"
        >
          Apply
        </Button>
      </div>
    </div>
  );
}

