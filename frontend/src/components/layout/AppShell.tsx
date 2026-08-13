import { Outlet, Link, useLocation, useNavigate } from "react-router-dom";
import { LayoutGrid, ListChecks, BarChart3, LogOut, User, ShieldCheck, Users, KeyRound, Settings, Activity } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import clsx from "clsx";
import { useAuth } from "@/contexts/AuthContext";

export function AppShell() {
  const loc = useLocation();
  const nav = useNavigate();
  const { user, logout, hasPermission, isAdmin } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // 点击外部关闭菜单
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    if (menuOpen) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [menuOpen]);

  if (!user) return null;

  const NAV = [
    { path: "/", label: "持仓看板", icon: LayoutGrid, perm: "dashboard:view" as const },
    { path: "/funds", label: "基金列表", icon: ListChecks, perm: "funds:view" as const },
    { path: "/stocks", label: "股票列表", icon: BarChart3, perm: "stocks:view" as const },
  ];

  return (
    <div className="flex flex-col h-full">
      <header className="page-header border-b border-slate-200 bg-white">
        <div className="px-3 sm:px-4 py-2 flex items-center justify-between gap-2">
          <h1 className="text-[13px] sm:text-[14px] font-semibold text-slate-800 tracking-wide truncate">
            主力基金持仓分析
          </h1>
          <nav className="flex items-center gap-0.5 sm:gap-1 shrink-0">
            {NAV.filter((n) => hasPermission(n.perm)).map((n) => {
              const active = n.path === "/" ? loc.pathname === "/" : loc.pathname.startsWith(n.path);
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

            {/* 用户菜单 */}
            <div className="relative ml-1" ref={menuRef}>
              <button
                onClick={() => setMenuOpen((o) => !o)}
                className="flex items-center gap-1 rounded text-[12px] px-2 py-1 text-slate-600 hover:bg-slate-50"
              >
                <div className="w-5 h-5 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center text-white text-[10px] font-medium">
                  {user.username.slice(0, 1).toUpperCase()}
                </div>
                <span className="hidden md:inline">{user.profile?.display_name || user.username}</span>
                {isAdmin && <ShieldCheck className="w-3 h-3 text-blue-500" />}
              </button>

              {menuOpen && (
                <div className="absolute right-0 top-full mt-1 w-44 rounded-md border border-slate-200 bg-white shadow-lg z-50 text-[12px]">
                  <div className="px-3 py-2 border-b border-slate-100">
                    <div className="font-medium text-slate-800">{user.username}</div>
                    <div className="text-[10px] text-slate-400">{user.email}</div>
                    <div className="mt-1 flex flex-wrap gap-0.5">
                      {user.roles.map((r) => (
                        <span
                          key={r.id}
                          className="text-[9px] rounded bg-blue-50 text-blue-700 px-1 py-0.5"
                        >
                          {r.name}
                        </span>
                      ))}
                    </div>
                  </div>
                  <Link
                    to="/profile"
                    onClick={() => setMenuOpen(false)}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-slate-700 hover:bg-slate-50"
                  >
                    <User className="w-3 h-3" /> 个人中心
                  </Link>
                  {hasPermission("settings:view") && (
                    <Link
                      to="/settings"
                      onClick={() => setMenuOpen(false)}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-slate-700 hover:bg-slate-50"
                    >
                      <Settings className="w-3 h-3" /> 抓取策略
                    </Link>
                  )}
                  {hasPermission("users:view") && (
                    <Link
                      to="/admin/users"
                      onClick={() => setMenuOpen(false)}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-slate-700 hover:bg-slate-50"
                    >
                      <Users className="w-3 h-3" /> 用户管理
                    </Link>
                  )}
                  {hasPermission("roles:view") && (
                    <Link
                      to="/admin/roles"
                      onClick={() => setMenuOpen(false)}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-slate-700 hover:bg-slate-50"
                    >
                      <KeyRound className="w-3 h-3" /> 角色权限
                    </Link>
                  )}
                  <button
                    onClick={async () => {
                      setMenuOpen(false);
                      await logout();
                      nav("/login", { replace: true });
                    }}
                    className="w-full text-left flex items-center gap-1.5 px-3 py-1.5 text-red-600 hover:bg-red-50 border-t border-slate-100"
                  >
                    <LogOut className="w-3 h-3" /> 退出登录
                  </button>
                </div>
              )}
            </div>
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
