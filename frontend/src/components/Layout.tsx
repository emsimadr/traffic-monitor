import { NavLink } from "react-router-dom";
import StatusBar from "./StatusBar";

const navLinks = [
  { to: "/", label: "Dashboard" },
  { to: "/trends", label: "Trends" },
  { to: "/config", label: "Configure" },
  { to: "/health", label: "Health" },
  { to: "/logs", label: "Logs" },
];

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <div className="font-semibold tracking-tight">Traffic Monitor</div>
          <nav className="flex items-center gap-2 text-sm text-slate-300">
            {navLinks.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) =>
                  `rounded px-3 py-2 hover:bg-slate-800 ${isActive ? "bg-slate-800 text-white" : ""}`
                }
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <StatusBar />
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </div>
  );
}

