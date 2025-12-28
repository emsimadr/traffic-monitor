import { cn } from "../../lib/utils";

type Props = React.TextareaHTMLAttributes<HTMLTextAreaElement>;

export const Textarea = ({ className, ...props }: Props) => (
  <textarea
    className={cn(
      "w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-600",
      className
    )}
    {...props}
  />
);

