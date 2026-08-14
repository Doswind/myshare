import { ChevronLeft, ChevronRight } from "lucide-react";

/** 通用分页组件：支持上一页/下一页 + 页码数字选择 */
export function Pagination({
  page,
  totalPages,
  total,
  pageSize,
  onPageChange,
}: {
  page: number;
  totalPages: number;
  total: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}) {
  if (total <= pageSize) return null;

  // 生成页码列表：当前页前后各2页，首尾各1页，中间用省略号
  const pages: (number | string)[] = [];
  const showAround = 2;
  for (let i = 1; i <= totalPages; i++) {
    if (i === 1 || i === totalPages || (i >= page - showAround && i <= page + showAround)) {
      pages.push(i);
    } else if (pages[pages.length - 1] !== "...") {
      pages.push("...");
    }
  }

  return (
    <div className="flex items-center justify-between px-3 py-2 border-t border-slate-100 text-[11px] text-slate-500">
      <span>
        第 {page} / {totalPages} 页 · 共 {total} 条
      </span>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPageChange(Math.max(1, page - 1))}
          disabled={page <= 1}
          className="flex items-center gap-0.5 px-1.5 py-0.5 rounded border border-slate-300 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <ChevronLeft className="w-3 h-3" />
        </button>
        {pages.map((p, i) =>
          p === "..." ? (
            <span key={`ellipsis-${i}`} className="px-1 text-slate-400">…</span>
          ) : (
            <button
              key={p}
              onClick={() => onPageChange(p as number)}
              className={`min-w-[24px] px-1 py-0.5 rounded text-center tabular ${
                p === page
                  ? "bg-slate-700 text-white font-medium"
                  : "border border-slate-300 hover:bg-slate-50"
              }`}
            >
              {p}
            </button>
          )
        )}
        <button
          onClick={() => onPageChange(Math.min(totalPages, page + 1))}
          disabled={page >= totalPages}
          className="flex items-center gap-0.5 px-1.5 py-0.5 rounded border border-slate-300 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <ChevronRight className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
}
