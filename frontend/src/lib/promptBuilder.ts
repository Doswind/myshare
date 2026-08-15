/**
 * promptBuilder：把单只股票的因子/持仓拼成结构化提示词
 *
 * 设计原则：
 * - 与后端 _build_enriched_message 保持一致：同一只股无论前端 prefill 还是后端注入，
 *   模板都遵循 doc.md §5.5。
 * - 找不到该股时返回占位 prompt（不抛错，让 UI 仍可发送）。
 * - 数字格式化：百分位加 %，涨跌加正负号。
 */

export interface AnalysisFactor {
  pct_rank_1y: number;
  pct_rank_3y: number;
  drawdown_1y: number;
  vs_ma60_z: number;
  rsi_14: number;
  boll_pos: number;
  consecutive_down: number;
  volume_ratio_20d: number;
}

export interface CapitalInfo {
  fund_count: number;
  total_mv_yi: number;
  mv_change_pct_qoq: number | null;
  avg_fund_ret_1y: number;
  smart_money_index: number;
  funds_add?: number;
  funds_cut?: number;
  funds_new?: number;
  funds_exit?: number;
}

export interface Valuation {
  pe_ttm: number;
  pe_pct_rank_3y: number;
  pb: number;
}

export interface Trend {
  ma20_dir: string;
  ma60_dir: string;
  ma250_dir: string;
  ret_20d: number;
  ret_60d: number;
}

export interface Holder {
  fund_code: string;
  fund_name: string;
  scale_yi: number;
  ret_1y: number;
  ratio_net: number;
  market_value_wan: number;
}

export interface Candidate {
  code: string;
  name: string;
  industry: string;
  factors: AnalysisFactor;
  capital: CapitalInfo;
  valuation?: Valuation;
  trend: Trend;
  holders?: Holder[];
  latest_price?: number | null;
  market_cap_wan_yi?: number | null;
  direction?: "in" | "out" | null;
  reason?: string | null;
  data_as_of?: string;
}

// 数字格式化辅助函数（防御性：undefined/null → "—"，避免 React 渲染崩溃）
const fmt = (
  n: number | null | undefined,
  digits: number = 1,
  signed_: boolean = false,
): string => {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  const v = Number(n).toFixed(digits);
  if (signed_) return `${n >= 0 ? "+" : ""}${v}`;
  return v;
};
const pct = (n: number | null | undefined, digits = 1) => {
  const v = fmt(n, digits);
  return v === "—" ? "—" : `${v}%`;
};

/**
 * 预填给用户的「请求」消息（不含数据注入段，数据由后端 _build_enriched_message 拼上）。
 * 这样设计的原因：用户可以在对话框首条消息里写自己的提问，前端只负责拼客观数据上下文
 * 作为「系统补充」段；后端再把这个「系统补充」段拼接上去，避免用户编辑改动数据部分。
 *
 * 但为了简单（与后端保持一致模板），本函数直接返回完整 prompt（含数据段）。
 * 当用户在 UI 编辑后点发送，发送的就是这个字符串 —— 后端会再注入一遍同结构数据，
 * 这是冗余但保证对话总能带完整上下文。
 */
export function buildAnalysisPrompt(code: string, candidates: Candidate[]): string {
  const found = candidates.find((c) => c.code === code);

  if (!found) {
    return `请基于公开知识分析 A 股股票 ${code} 的投资价值，重点关注：
1. 主营业务、行业地位、竞争优势
2. 财务质量（盈利能力、现金流、负债）
3. 估值水平与历史区间对比
4. 近期催化剂与风险

请尽量结构化，便于人类快速阅读。

---
系统注：本系统未收录 ${code} 的因子与持仓数据，请基于通用知识回答。`;
  }

  const f = found.factors;
  const cap = found.capital;
  const tr = found.trend;
  const holders = found.holders ?? [];
  const holdersText = holders.length
    ? holders
        .map(
          (h) =>
            `  - ${h.fund_name}(${h.fund_code}) 规模${fmt(h.scale_yi, 0)}亿 近1年${pct(h.ret_1y)} 占比${pct(h.ratio_net)} 市值${fmt(h.market_value_wan, 0)}万`,
        )
        .join("\n")
    : "  （无持仓数据）";

  return `你是一名 A 股研究员。请基于以下系统提供的数据，给出对该股票的尽调结论。

【股票基本信息】
代码：${found.code}
名称：${found.name || "—"}
行业：${found.industry || "—"}
最新价：${fmt(found.latest_price)}
总市值：${fmt(found.market_cap_wan_yi)} 万亿

【位置因子（事实标注，非预测）】
近 1 年价格百分位：${pct(f.pct_rank_1y)}
近 3 年价格百分位：${pct(f.pct_rank_3y)}
距近 1 年高点回撤：${fmt(f.drawdown_1y, 1, true)}%
相对 MA60 的 z-score：${fmt(f.vs_ma60_z, 2)}
RSI(14)：${fmt(f.rsi_14, 1)}
布林带位置：${pct(f.boll_pos)}
连续下跌天数：${fmt(f.consecutive_down, 0)}
20 日均量比：${fmt(f.volume_ratio_20d, 2)}

【趋势与动量】
MA20 / MA60 / MA250：${tr.ma20_dir || "—"} / ${tr.ma60_dir || "—"} / ${tr.ma250_dir || "—"}
近 20 日收益率：${fmt(tr.ret_20d, 1, true)}%
近 60 日收益率：${fmt(tr.ret_60d, 1, true)}%

【主力资金行为（本系统独占，季度环比）】
持有该股的主力基金数：${fmt(cap.fund_count, 0)}
合计持仓市值：${fmt(cap.total_mv_yi, 1)} 亿
上季度环比加减仓：${cap.mv_change_pct_qoq === null || cap.mv_change_pct_qoq === undefined ? "新进建仓" : fmt(cap.mv_change_pct_qoq, 1, true) + "%"}
加仓 ${cap.funds_add ?? 0} 只 / 减仓 ${cap.funds_cut ?? 0} 只 / 新进 ${cap.funds_new ?? 0} 只 / 退出 ${cap.funds_exit ?? 0} 只
持仓基金近 1 年收益中位数：${pct(cap.avg_fund_ret_1y)}
持仓基金近 1 年跑赢比例：${fmt(cap.smart_money_index, 2)}

【重仓基金明细】
${holdersText}

请给出结构化结论（Markdown 格式）：
1. **整体判断**：看好 / 中性 / 谨慎
2. **看多逻辑**：3-5 条
3. **看空/风险**：3-5 条
4. **关键催化剂**：近期需要关注的变量
5. **数据缺口**：你希望看但系统未提供的数据

请尽量结构化，便于人类快速阅读。`;
}

/**
 * 从 OpenClaw SSE 事件中提取 text delta。
 *
 * 只接受真正的「增量」事件（类型以 .delta 结尾且带 string 类型的 delta 字段）。
 * response.completed / response.output_text.done 等汇总事件携带的是「全量文本」，
 * 若一并累加会导致内容重复输出，因此这里一律忽略。
 */
export function extractTextDelta(event: any): string {
  if (!event || typeof event !== "object") return "";
  const t = typeof event.type === "string" ? event.type : "";
  if (t.endsWith(".delta") && typeof event.delta === "string") return event.delta;
  return "";
}

/** 从 OpenClaw SSE 事件中提取 response id（用于多轮 previous_response_id） */
export function extractResponseId(event: any): string | null {
  if (!event || typeof event !== "object") return null;
  if (event.type === "response.completed" && event.response?.id) return event.response.id;
  if (typeof event.id === "string") return event.id;
  if (event.response?.id) return event.response.id;
  return null;
}