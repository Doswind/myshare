import { Outlet, Link, useLocation } from "react-router-dom";
import { LayoutGrid, ListChecks, Settings, BarChart3, Activity } from "lucide-react";
import clsx from "clsx";

const NAV = [
  { path: "/", label: "持仓看板", icon: LayoutGrid },
  { path: "/funds", label: "基金列表", icon: ListChecks },
  { path: "/stocks", label: "股票列表", icon: BarChart3 },
  { path: "/settings", label: "设置", icon: Settings },
];

export function AppShell() {
  const loc = useLocation();
  return (
    <div className="flex flex-col h-full">
      <header className="page-header border-b border-slate-200 bg-white">
        <div className="px-3 sm:px-4 py-2 flex items-center justify-between gap-2">
          <h1 className="text-[13px] sm:text-[14px] font-semibold text-slate-800 tracking-wide truncate">
            主力基金持仓分析
          </h1>
          <nav className="flex items-center gap-0.5 sm:gap-1 shrink-0">
            {NAV.map((n) => {
              const active =
                n.path === "/" ? loc.pathname === "/" : loc.pathname.startsWith(n.path);
              const Icon = n.icon;
              return (
                <Link
                  key={n.path}
                  to={n.path}
                  className={clsx(
                    "flex items-center gap-1 rounded text-[12px] transition-colors",
                    "px-2 sm:px-2.5 py-1",
                    active
                      ? "bg-slate-100 text-slate-900 font-medium"
                      : "text-slate-500 hover:text-slate-800 hover:bg-slate-50"
                  )}
                >
                  <Icon className="w-3.5 h-3.5 shrink-0" />
                  <span className="hidden sm:inline">{n.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>
      </header>
      <main className="page-main flex-1 overflow-auto p-2 sm:p-3">
        <Outlet />
      </main>
      <footer className="border-t border-slate-200 bg-white px-3 sm:px-4 py-1 text-[10px] text-slate-400 flex items-center gap-1">
        <Activity className="w-2.5 h-2.5" />
        数据来源：东方财富 · 仅供研究参考
      </footer>
    </div>
  );
}
