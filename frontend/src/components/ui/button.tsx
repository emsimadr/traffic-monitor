import { cn } from "../../lib/utils";

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "outline" };

export function Button({ className, variant = "primary", ...props }: Props) {
  const base = "inline-flex items-center justify-center rounded-lg px-3 py-2 text-sm font-medium transition";
  const variants: Record<string, string> = {
    primary: "bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-50",
    ghost: "text-slate-200 hover:bg-slate-800 disabled:opacity-50",
    outline: "border border-slate-700 text-slate-100 hover:bg-slate-800 disabled:opacity-50",
  };
  return <button className={cn(base, variants[variant], className)} {...props} />;
}

