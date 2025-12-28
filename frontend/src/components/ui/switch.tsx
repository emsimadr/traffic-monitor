import { cn } from "../../lib/utils";

type Props = {
  checked: boolean;
  onChange: (v: boolean) => void;
  label?: string;
};

export function Switch({ checked, onChange, label }: Props) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-200">
      <div
        className={cn(
          "relative inline-flex h-5 w-9 items-center rounded-full transition",
          checked ? "bg-blue-600" : "bg-slate-700"
        )}
        onClick={() => onChange(!checked)}
      >
        <span
          className={cn(
            "inline-block h-4 w-4 transform rounded-full bg-white transition",
            checked ? "translate-x-4" : "translate-x-1"
          )}
        />
      </div>
      {label && <span className="text-slate-300">{label}</span>}
    </label>
  );
}

