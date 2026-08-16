import clsx from "clsx";

interface RangeSliderProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  suffix?: string;
  onChange: (v: number) => void;
}

export function RangeSlider({
  label,
  value,
  min,
  max,
  step = 1,
  suffix = "",
  onChange,
}: RangeSliderProps) {
  return (
    <div className="flex items-center gap-2 w-full sm:min-w-[180px]">
      <span className="text-[11px] text-slate-500 whitespace-nowrap">{label}</span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="flex-1 accent-slate-700 h-1 cursor-pointer"
      />
      <span className="text-[12px] text-slate-800 tabular w-12 text-right">
        {value}
        {suffix}
      </span>
    </div>
  );
}

interface DoubleRangeSliderProps {
  label: string;
  valueMin: number | null;
  valueMax: number | null;
  min: number;
  max: number;
  step?: number;
  suffix?: string;
  onChange: (min: number | null, max: number | null) => void;
}

export function DoubleRangeSlider({
  label,
  valueMin,
  valueMax,
  min,
  max,
  step = 1,
  suffix = "",
  onChange,
}: DoubleRangeSliderProps) {
  // 完全受控：显示值直接来自 props（store），异步恢复偏好后能正确回填。
  // 空字符串视为「不限」(null)。
  return (
    <div className="flex items-center gap-2 w-full sm:min-w-[220px]">
      <span className="text-[11px] text-slate-500 whitespace-nowrap">{label}</span>
      <input
        type="number"
        value={valueMin ?? ""}
        min={min}
        max={valueMax ?? max}
        step={step}
        onChange={(e) => {
          const v = e.target.value === "" ? null : Number(e.target.value);
          onChange(v, valueMax);
        }}
        className="w-16 px-1.5 py-0.5 text-[12px] border border-slate-300 rounded tabular"
        placeholder="不限"
      />
      <span className="text-slate-400">~</span>
      <input
        type="number"
        value={valueMax ?? ""}
        min={valueMin ?? min}
        max={max}
        step={step}
        onChange={(e) => {
          const v = e.target.value === "" ? null : Number(e.target.value);
          onChange(valueMin, v);
        }}
        className="w-16 px-1.5 py-0.5 text-[12px] border border-slate-300 rounded tabular"
        placeholder="不限"
      />
      <span className="text-[11px] text-slate-400">{suffix}</span>
    </div>
  );
}

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  className?: string;
}

export function Modal({ open, onClose, title, children, className }: ModalProps) {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 supports-[backdrop-filter]:backdrop-blur-[1px] animate-in fade-in"
      onClick={onClose}
    >
      <div
        className={clsx(
          "rounded-md bg-white p-4 shadow-lg max-w-[90vw] max-h-[85vh] overflow-auto",
          "border border-slate-200",
          className
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {title && (
          <div className="text-sm font-semibold text-slate-800 mb-3 pb-2 border-b border-slate-100">
            {title}
          </div>
        )}
        {children}
      </div>
    </div>
  );
}

export function Spinner() {
  return (
    <div className="inline-block w-3 h-3 border-2 border-slate-300 border-t-slate-600 rounded-full animate-spin" />
  );
}
