import { useEffect, useRef, useState } from "react";
import { init, dispose, LineType, PolygonType, TooltipShowRule, type Chart } from "klinecharts";

interface Props {
  bars: KLineBarLike[];
  height?: number;
  /** 股票名称（用于自定义中文图例，可选） */
  stockName?: string;
}

interface KLineBarLike {
  日期: string;
  开盘?: number | null;
  最高?: number | null;
  最低?: number | null;
  收盘?: number | null;
  成交量?: number | null;
  换手率?: number | null;
}

const MA_PERIODS = [5, 10, 20, 30, 60];

/** 计算最近 N 根的简单移动平均（基于收盘价） */
function computeMA(bars: KLineBarLike[], period: number): number | null {
  if (!bars || bars.length < period) return null;
  const slice = bars.slice(-period);
  const closes = slice.map((b) => Number(b.收盘 ?? 0));
  const valid = closes.filter((c) => c > 0);
  if (valid.length < period) return null;
  return valid.reduce((s, c) => s + c, 0) / valid.length;
}

/**
 * 东财风格 K 线图：浅色主题 + 红涨绿跌 + MA 叠加 + VOL 副图 + 中文图例
 *
 * 配色约定（中国 A 股）：红涨绿跌
 * - 均线5 黄 / 均线10 橙 / 均线20 粉 / 均线30 紫红 / 均线60 绿
 */
export function KLineChart({ bars, height = 480, stockName }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<Chart | null>(null);
  const overlayRef = useRef<HTMLDivElement | null>(null);
  // 十字光标所在 K 线的下标；null 表示未悬浮（默认展示最后一根）
  const [activeIndex, setActiveIndex] = useState<number | null>(null);

  // 挂载 + 设置主题 + 创建指标
  useEffect(() => {
    if (!containerRef.current) return;
    const chart = init(containerRef.current);
    if (!chart) return;
    chartRef.current = chart;

    // 1) 全局样式：浅色 + 红涨绿跌 + 网格
    chart.setStyles({
      grid: {
        show: true,
        horizontal: { show: true, style: LineType.Dashed, dashedValue: [4, 4], color: "#e5e7eb", size: 1 },
        vertical: { show: true, style: LineType.Dashed, dashedValue: [4, 4], color: "#e5e7eb", size: 1 },
      },
      candle: {
        bar: {
          // 中国 A 股配色：红涨绿跌
          upColor: "#E63946",
          downColor: "#1BAB66",
          noChangeColor: "#888888",
          upBorderColor: "#E63946",
          downBorderColor: "#1BAB66",
          noChangeBorderColor: "#888888",
          upWickColor: "#E63946",
          downWickColor: "#1BAB66",
          noChangeWickColor: "#888888",
        },
        // 关掉内置 K 线 tooltip（用我们自己的中文图例代替）
        tooltip: { showRule: TooltipShowRule.None },
      },
      indicator: {
        // 关掉内置 last value 标签 + indicator tooltip（用我们自己的中文图例）
        lastValueMark: { show: false },
        tooltip: { showRule: TooltipShowRule.None },
        bars: [{ style: PolygonType.Fill, borderStyle: LineType.Solid, borderSize: 1, borderDashedValue: [2, 2] }],
        lines: [{ style: LineType.Solid, size: 1, smooth: false, dashedValue: [2, 2] }],
        circles: [{ style: PolygonType.Fill, borderStyle: LineType.Solid, borderSize: 1 }],
      },
      xAxis: {
        axisLine: { show: true, color: "#cbd5e1", size: 1 },
        tickText: { show: true, color: "#64748b", size: 10 },
        tickLine: { show: true, length: 4, color: "#cbd5e1" },
      },
      yAxis: {
        axisLine: { show: true, color: "#cbd5e1", size: 1 },
        tickText: { show: true, color: "#64748b", size: 10 },
        tickLine: { show: true, length: 4, color: "#cbd5e1" },
      },
      crosshair: {
        horizontal: { show: true, line: { show: true, style: LineType.Dashed, dashedValue: [4, 4], color: "#94a3b8", size: 1 } },
        vertical: { show: true, line: { show: true, style: LineType.Dashed, dashedValue: [4, 4], color: "#94a3b8", size: 1 } },
      },
    });

    // 2) 创建 MA 指标（用一组 calcParams 自动叠加 5/10/20/30/60）
    chart.createIndicator(
      { name: "MA", calcParams: MA_PERIODS },
      false,
      { id: "candle_pane" },
    );

    // 3) VOL 副图
    chart.createIndicator("VOL");

    // 4) 订阅十字光标：悬浮时顶部图例展示该根 K 线，移出后回落到最后一根
    chart.subscribeAction("onCrosshairChange" as any, (param: any) => {
      const idx = param?.dataIndex;
      setActiveIndex(typeof idx === "number" && idx >= 0 ? idx : null);
    });

    return () => {
      if (containerRef.current) {
        dispose(containerRef.current);
      }
      chartRef.current = null;
    };
  }, []);

  // 数据更新（bars 变化时）
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    if (!bars || bars.length === 0) return;
    const data = bars.map((b) => ({
      timestamp: new Date(b.日期).getTime(),
      open: Number(b.开盘 ?? 0),
      high: Number(b.最高 ?? 0),
      low: Number(b.最低 ?? 0),
      close: Number(b.收盘 ?? 0),
      volume: Number(b.成交量 ?? 0),
    }));
    chart.applyNewData(data, false);
  }, [bars]);

  // 计算自定义中文图例
  const maValues = MA_PERIODS.map((p) => ({ period: p, value: computeMA(bars, p) }));
  const maColors: Record<number, string> = {
    5: "#F0B400",   // 黄
    10: "#FF8800",  // 橙
    20: "#E91E63",  // 粉
    30: "#9C27B0",  // 紫红
    60: "#1BAB66",  // 绿
  };

  // 当前展示的 K 线：悬浮取十字光标位置，否则取最后一根
  const dispIdx =
    activeIndex !== null && activeIndex >= 0 && activeIndex < bars.length
      ? activeIndex
      : bars.length - 1;
  const cur = bars[dispIdx];
  const prev = dispIdx > 0 ? bars[dispIdx - 1] : undefined;
  const num = (v: unknown) => (v === null || v === undefined ? null : Number(v));
  const open = num(cur?.开盘);
  const high = num(cur?.最高);
  const low = num(cur?.最低);
  const close = num(cur?.收盘);
  const turnover = num(cur?.换手率);
  const prevClose = num(prev?.收盘);
  const change =
    close !== null && prevClose !== null && prevClose !== 0 ? close - prevClose : null;
  const changePct =
    change !== null && prevClose !== null && prevClose !== 0
      ? (change / prevClose) * 100
      : null;
  // 红涨绿跌
  const chgColor = change === null ? "#64748b" : change >= 0 ? "#E63946" : "#1BAB66";
  const fmt = (v: number | null) => (v === null ? "—" : v.toFixed(2));
  const fmtSigned = (v: number | null, suffix = "") =>
    v === null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}${suffix}`;

  return (
    <div className="relative" style={{ width: "100%", height }}>
      <div
        ref={containerRef}
        style={{ width: "100%", height }}
        className="kline-container bg-white"
      />
      {/* 中文图例：覆盖 klinecharts 自带的 MA 图例，定位在图顶部 */}
      <div
        ref={overlayRef}
        className="absolute top-1 left-2 right-2 pointer-events-none flex flex-col gap-0.5 text-[11px] z-10"
      >
        {stockName && (
          <div className="flex items-center gap-3">
            <span className="text-slate-800 font-medium">{stockName}</span>
            {cur?.日期 && (
              <span className="text-slate-500 tabular">{cur.日期}</span>
            )}
          </div>
        )}
        {cur && (
          <div className="flex items-center gap-2.5 flex-wrap tabular">
            <span className="text-slate-500">开盘<span className="ml-0.5" style={{ color: chgColor }}>{fmt(open)}</span></span>
            <span className="text-slate-500">收盘<span className="ml-0.5" style={{ color: chgColor }}>{fmt(close)}</span></span>
            <span className="text-slate-500">最高<span className="ml-0.5" style={{ color: chgColor }}>{fmt(high)}</span></span>
            <span className="text-slate-500">最低<span className="ml-0.5" style={{ color: chgColor }}>{fmt(low)}</span></span>
            <span className="text-slate-500">涨跌额<span className="ml-0.5" style={{ color: chgColor }}>{fmtSigned(change)}</span></span>
            <span className="text-slate-500">涨跌幅<span className="ml-0.5" style={{ color: chgColor }}>{fmtSigned(changePct, "%")}</span></span>
            <span className="text-slate-500">换手率<span className="ml-0.5 text-slate-700">{turnover === null ? "—" : `${turnover.toFixed(2)}%`}</span></span>
          </div>
        )}
        {maValues.some((m) => m.value !== null) && (
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-slate-500">MA({MA_PERIODS.join(",")})</span>
            {maValues.map((m) =>
              m.value !== null ? (
                <span key={m.period} className="flex items-center gap-1">
                  <span style={{ color: maColors[m.period] }}>MA{m.period}</span>
                  <span className="tabular text-slate-700">{m.value.toFixed(2)}</span>
                </span>
              ) : null,
            )}
          </div>
        )}
      </div>
    </div>
  );
}