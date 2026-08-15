import { useCallback, useEffect, useRef, useState } from "react";
import { searchStocks } from "@/api/watchlist";
import { fetchIndustryNames } from "@/api/stocks";

/**
 * #/$// 联想输入。
 *
 * - `#` 股票：调 /stocks/search（防抖 200ms），选中插入 `名称(代码) `
 * - `$` 板块：本地过滤行业名（首次拉取后缓存），选中插入 `板块 `
 * - `/` 命令：静态命令模板，选中插入对应文本
 *
 * 用法：把 onChange/onKeyDown/onSelectCommit 接到 textarea，把 popup 渲染在输入框上方。
 * onKeyDown 返回 true 表示按键已被联想框消费（parent 应跳过发送/换行）。
 */

export interface MentionItem {
  /** 展示主文本 */
  label: string;
  /** 展示副文本（可选） */
  sub?: string;
  /** 选中后插入到输入框的文本（替换触发 token，末尾自带空格） */
  insert: string;
}

type Trigger = "#" | "$" | "/";

const COMMANDS: MentionItem[] = [
  { label: "/分析", sub: "请分析这只股票的投资价值", insert: "请分析这只股票的投资价值：" },
  { label: "/看多", sub: "列出看多逻辑", insert: "请列出看多逻辑（3-5 条）：" },
  { label: "/看空", sub: "列出看空/风险", insert: "请列出看空逻辑与主要风险（3-5 条）：" },
  { label: "/总结", sub: "总结要点", insert: "请用要点总结上文：" },
  { label: "/对比", sub: "对比两只标的", insert: "请对比以下标的的优劣：" },
  { label: "/风险", sub: "风险提示", insert: "请给出该标的的主要风险提示：" },
];

interface TriggerState {
  trigger: Trigger;
  start: number; // 触发符在字符串中的下标
  query: string;
}

/** 从光标前文本里识别触发 token（触发符须在行首或前面是空白） */
function detectTrigger(text: string, caret: number): TriggerState | null {
  const before = text.slice(0, caret);
  // 从光标往前找最近的触发符
  for (let i = before.length - 1; i >= 0; i--) {
    const ch = before[i];
    if (ch === " " || ch === "\n" || ch === "\t") return null; // 遇到空白，token 结束，无触发
    if (ch === "#" || ch === "$" || ch === "/") {
      const prev = i > 0 ? before[i - 1] : "";
      if (i === 0 || prev === " " || prev === "\n" || prev === "\t") {
        return { trigger: ch as Trigger, start: i, query: before.slice(i + 1) };
      }
      return null;
    }
  }
  return null;
}

export function useMention(
  value: string,
  setValue: (v: string) => void,
  textareaRef: React.RefObject<HTMLTextAreaElement>,
) {
  const [items, setItems] = useState<MentionItem[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<TriggerState | null>(null);
  const debounceRef = useRef<number | null>(null);
  const industriesRef = useRef<string[] | null>(null);

  const close = useCallback(() => {
    setOpen(false);
    setItems([]);
    setActiveIndex(0);
    triggerRef.current = null;
    if (debounceRef.current) {
      window.clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }
  }, []);

  const recompute = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    const caret = el.selectionStart ?? value.length;
    const t = detectTrigger(value, caret);
    if (!t) {
      close();
      return;
    }
    triggerRef.current = t;
    setActiveIndex(0);

    if (t.trigger === "/") {
      const q = t.query.toLowerCase();
      const filtered = COMMANDS.filter((c) => c.label.toLowerCase().includes(q));
      setItems(filtered);
      setOpen(filtered.length > 0);
      return;
    }

    if (t.trigger === "$") {
      const apply = (names: string[]) => {
        const q = t.query;
        const filtered = names
          .filter((n) => (q ? n.includes(q) : true))
          .slice(0, 12)
          .map<MentionItem>((n) => ({ label: n, insert: `$${n} ` }));
        setItems(filtered);
        setOpen(filtered.length > 0);
      };
      if (industriesRef.current) {
        apply(industriesRef.current);
      } else {
        fetchIndustryNames()
          .then((rows) => {
            industriesRef.current = rows.map((r) => r.name);
            if (triggerRef.current?.trigger === "$") apply(industriesRef.current);
          })
          .catch(() => {
            /* ignore */
          });
      }
      return;
    }

    // '#' 股票：防抖搜索
    const q = t.query.trim();
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    if (!q) {
      setItems([]);
      setOpen(false);
      return;
    }
    debounceRef.current = window.setTimeout(() => {
      searchStocks(q, 8)
        .then((hits) => {
          if (triggerRef.current?.trigger !== "#") return;
          const mapped = hits.map<MentionItem>((h) => ({
            label: h.name,
            sub: `${h.code}${h.industry_name ? " · " + h.industry_name : ""}`,
            insert: `#${h.name}(${h.code}) `,
          }));
          setItems(mapped);
          setOpen(mapped.length > 0);
        })
        .catch(() => {
          /* ignore */
        });
    }, 200);
  }, [value, textareaRef, close]);

  // value 变化时重算
  useEffect(() => {
    recompute();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const commit = useCallback(
    (item: MentionItem) => {
      const t = triggerRef.current;
      const el = textareaRef.current;
      if (!t || !el) return;
      const caret = el.selectionStart ?? value.length;
      const nextVal = value.slice(0, t.start) + item.insert + value.slice(caret);
      setValue(nextVal);
      close();
      // 光标移到插入内容末尾
      const nextCaret = t.start + item.insert.length;
      requestAnimationFrame(() => {
        el.focus();
        el.setSelectionRange(nextCaret, nextCaret);
      });
    },
    [value, setValue, textareaRef, close],
  );

  /** 返回 true 表示消费了此按键 */
  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>): boolean => {
      if (!open || items.length === 0) return false;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIndex((i) => (i + 1) % items.length);
        return true;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIndex((i) => (i - 1 + items.length) % items.length);
        return true;
      }
      if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        commit(items[activeIndex]);
        return true;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        close();
        return true;
      }
      return false;
    },
    [open, items, activeIndex, commit, close],
  );

  const popup =
    open && items.length > 0 ? (
      <div className="absolute bottom-full left-0 mb-1 w-72 max-h-56 overflow-auto rounded-md border border-slate-200 bg-white shadow-lg z-10 py-1">
        {items.map((it, i) => (
          <button
            key={it.label + i}
            type="button"
            onMouseDown={(e) => {
              e.preventDefault();
              commit(it);
            }}
            className={
              "w-full text-left px-2.5 py-1.5 text-[12px] flex items-center justify-between gap-2 " +
              (i === activeIndex ? "bg-blue-50 text-blue-700" : "text-slate-700 hover:bg-slate-50")
            }
          >
            <span className="truncate">{it.label}</span>
            {it.sub && <span className="text-[10px] text-slate-400 shrink-0">{it.sub}</span>}
          </button>
        ))}
      </div>
    ) : null;

  return { popup, onKeyDown, open, close };
}
