// 通用确认弹窗（替代浏览器原生 confirm）
import { AlertTriangle, X } from "lucide-react";
import type { ReactNode } from "react";

export type ConfirmVariant = "danger" | "warning" | "info";

export interface ConfirmOptions {
  title: ReactNode;
  description?: ReactNode;
  confirmText?: string;
  cancelText?: string;
  variant?: ConfirmVariant;
}

interface ConfirmDialogProps extends ConfirmOptions {
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

const VARIANT_STYLES: Record<ConfirmVariant, { icon: string; btn: string }> = {
  danger: {
    icon: "bg-red-100 text-red-600",
    btn: "bg-red-600 hover:bg-red-700",
  },
  warning: {
    icon: "bg-amber-100 text-amber-600",
    btn: "bg-amber-600 hover:bg-amber-700",
  },
  info: {
    icon: "bg-blue-100 text-blue-600",
    btn: "bg-blue-600 hover:bg-blue-700",
  },
};

export function ConfirmDialog({
  open,
  title,
  description,
  confirmText = "确定",
  cancelText = "取消",
  variant = "info",
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!open) return null;
  const v = VARIANT_STYLES[variant];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-[1px] p-4"
      onClick={onCancel}
    >
      <div
        className="w-full max-w-sm rounded-md border border-slate-200 bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-3 px-4 pt-4">
          <div className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${v.icon}`}>
            <AlertTriangle className="w-4 h-4" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-[13px] font-semibold text-slate-800 leading-snug">{title}</h3>
            {description && (
              <div className="text-[12px] text-slate-500 mt-1 leading-relaxed whitespace-pre-line">
                {description}
              </div>
            )}
          </div>
          <button
            onClick={onCancel}
            className="shrink-0 text-slate-400 hover:text-slate-700 -mt-0.5"
            aria-label="关闭"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="flex justify-end gap-2 px-4 py-3 mt-2 border-t border-slate-100">
          <button
            onClick={onCancel}
            className="text-[12px] px-3 py-1.5 rounded border border-slate-300 text-slate-700 hover:bg-slate-50"
          >
            {cancelText}
          </button>
          <button
            onClick={onConfirm}
            className={`text-[12px] px-3 py-1.5 rounded text-white ${v.btn}`}
            autoFocus
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}
