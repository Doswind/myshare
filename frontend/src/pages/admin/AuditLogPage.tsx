import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { auditApi } from "@/api/auth";
import { CheckCircle2, AlertCircle, Search } from "lucide-react";
import { Pagination } from "@/components/common/Pagination";
import type { AuditLog } from "@/types/api";

const ACTION_LABELS: Record<string, string> = {
  login: "登录",
  logout: "登出",
  refresh_token: "刷新Token",
  change_password: "修改密码",
  reset_password: "重置密码",
  create_user: "创建用户",
  update_user: "更新用户",
  delete_user: "删除用户",
  admin_reset_password: "管理员重置密码",
  request_password_reset: "申请密码重置",
};

export default function AuditLogPage() {
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [filterAction, setFilterAction] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterUsername, setFilterUsername] = useState("");
  const [searchInput, setSearchInput] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["audit-logs", page, pageSize, filterAction, filterStatus, filterUsername],
    queryFn: () =>
      auditApi.list({
        page,
        page_size: pageSize,
        action: filterAction || undefined,
        status: filterStatus || undefined,
        username: filterUsername || undefined,
      }),
    refetchInterval: 30_000,
  });

  const logs: AuditLog[] = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const handleSearch = () => {
    setFilterUsername(searchInput.trim());
    setPage(1);
  };

  return (
    <div className="space-y-3 max-w-5xl">
      {/* 筛选 */}
      <div className="rounded-md border border-slate-200 bg-white p-3">
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-1.5">
            <span className="text-[12px] text-slate-500">操作</span>
            <select
              value={filterAction}
              onChange={(e) => { setFilterAction(e.target.value); setPage(1); }}
              className="px-1.5 py-0.5 border border-slate-300 rounded text-[12px]"
            >
              <option value="">全部</option>
              {Object.entries(ACTION_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[12px] text-slate-500">状态</span>
            <select
              value={filterStatus}
              onChange={(e) => { setFilterStatus(e.target.value); setPage(1); }}
              className="px-1.5 py-0.5 border border-slate-300 rounded text-[12px]"
            >
              <option value="">全部</option>
              <option value="success">成功</option>
              <option value="failed">失败</option>
            </select>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[12px] text-slate-500">用户</span>
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder="用户名"
              className="w-28 px-1.5 py-0.5 border border-slate-300 rounded text-[12px]"
            />
            <button
              onClick={handleSearch}
              className="flex items-center gap-1 px-2 py-0.5 rounded bg-slate-700 text-white text-[11px] hover:bg-slate-800"
            >
              <Search className="w-3 h-3" /> 搜索
            </button>
          </div>
          {(filterAction || filterStatus || filterUsername) && (
            <button
              onClick={() => {
                setFilterAction(""); setFilterStatus(""); setFilterUsername(""); setSearchInput("");
                setPage(1);
              }}
              className="px-2 py-0.5 rounded border border-slate-300 text-slate-600 text-[11px] hover:bg-slate-50"
            >
              清除筛选
            </button>
          )}
        </div>
      </div>

      {/* 日志表格 */}
      <div className="rounded-md border border-slate-200 bg-white overflow-hidden">
        <div className="px-3 py-2 border-b border-slate-100 text-[12px] text-slate-700 font-medium">
          审计日志（共 {total} 条）
        </div>
        <table className="w-full text-[12px]">
          <thead className="bg-slate-50 text-slate-500 text-[11px]">
            <tr>
              <th className="text-left px-3 py-1.5 font-normal">时间</th>
              <th className="text-left px-3 py-1.5 font-normal">用户</th>
              <th className="text-left px-3 py-1.5 font-normal">操作</th>
              <th className="text-left px-3 py-1.5 font-normal">目标</th>
              <th className="text-left px-3 py-1.5 font-normal">状态</th>
              <th className="text-left px-3 py-1.5 font-normal">IP</th>
              <th className="text-left px-3 py-1.5 font-normal">详情</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={7} className="text-center text-slate-400 py-4">加载中…</td></tr>
            )}
            {logs.length === 0 && !isLoading && (
              <tr><td colSpan={7} className="text-center text-slate-400 py-4">暂无日志</td></tr>
            )}
            {logs.map((log) => (
              <tr key={log.id} className="border-t border-slate-100 hover:bg-slate-50">
                <td className="px-3 py-1.5 tabular text-slate-500">
                  {formatBeijingTime(log.created_at)}
                </td>
                <td className="px-3 py-1.5 text-slate-800">{log.username || "--"}</td>
                <td className="px-3 py-1.5 text-slate-700">
                  {ACTION_LABELS[log.action] || log.action}
                </td>
                <td className="px-3 py-1.5 text-slate-600 truncate max-w-[120px]" title={log.target}>
                  {log.target || "--"}
                </td>
                <td className="px-3 py-1.5">
                  <span className={`inline-flex items-center gap-1 text-[11px] ${
                    log.status === "success" ? "text-emerald-600" : "text-red-600"
                  }`}>
                    {log.status === "success" ? (
                      <CheckCircle2 className="w-3 h-3" />
                    ) : (
                      <AlertCircle className="w-3 h-3" />
                    )}
                    {log.status}
                  </span>
                </td>
                <td className="px-3 py-1.5 tabular text-slate-500">{log.ip || "--"}</td>
                <td className="px-3 py-1.5 text-slate-500 text-[11px] truncate max-w-[200px]" title={log.detail}>
                  {log.detail || "--"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <Pagination
          page={page}
          totalPages={totalPages}
          total={total}
          pageSize={pageSize}
          onPageChange={setPage}
        />
      </div>
    </div>
  );
}

/** ISO 时间 → 北京时间格式化 */
function formatBeijingTime(iso?: string): string {
  if (!iso) return "--";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "--";
  const dateStr = d.toLocaleDateString("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric", month: "numeric", day: "numeric",
  });
  const timeStr = d.toLocaleTimeString("zh-CN", {
    timeZone: "Asia/Shanghai", hour12: false,
  });
  const todayStr = new Date().toLocaleDateString("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric", month: "numeric", day: "numeric",
  });
  if (dateStr === todayStr) return timeStr;
  return `${dateStr} ${timeStr}`;
}
