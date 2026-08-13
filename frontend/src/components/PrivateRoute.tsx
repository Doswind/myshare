// 路由守卫：未登录跳 /login；无权限显示 403
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import type { ReactNode } from "react";

export function PrivateRoute({ children, permission }: { children: ReactNode; permission?: string }) {
  const { user, loading, hasPermission } = useAuth();
  const loc = useLocation();
  if (loading) {
    return <div className="flex h-full items-center justify-center text-[12px] text-slate-400">加载中…</div>;
  }
  if (!user) {
    return <Navigate to="/login" state={{ from: loc.pathname }} replace />;
  }
  if (permission && !hasPermission(permission)) {
    return (
      <div className="flex h-full flex-col items-center justify-center text-center text-slate-400">
        <div className="text-3xl mb-2">🔒</div>
        <div className="text-[14px]">无权访问</div>
        <div className="text-[11px] mt-1">缺少权限：{permission}</div>
      </div>
    );
  }
  return <>{children}</>;
}
