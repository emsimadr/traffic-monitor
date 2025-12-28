import { cn } from "../../lib/utils";

type Tab = { id: string; label: string };

export function Tabs({
  tabs,
  active,
  onChange,
  children,
}: {
  tabs: Tab[];
  active: string;
  onChange: (id: string) => void;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className={cn(
              "rounded-lg px-3 py-2 text-sm font-medium",
              active === tab.id ? "bg-slate-800 text-white" : "text-slate-300 hover:bg-slate-800/60"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div>{children}</div>
    </div>
  );
}

