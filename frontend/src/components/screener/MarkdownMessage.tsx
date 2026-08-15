import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

/**
 * 统一的 Markdown 渲染组件。
 *
 * - 用 @tailwindcss/typography 的 prose 基础排版，再通过 components 覆写关键元素，
 *   保证在窄气泡里表格/代码块/列表不溢出、可横向滚动。
 * - skipHtml：不渲染原始 HTML，防注入。
 */
const components: Components = {
  // 表格：外层包一层横向滚动容器
  table: ({ children }) => (
    <div className="overflow-x-auto my-2">
      <table className="border-collapse text-[11px] w-full">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border border-slate-200 bg-slate-50 px-2 py-1 text-left font-medium">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border border-slate-200 px-2 py-1 align-top">{children}</td>
  ),
  // 代码：区分行内 code 与块级 pre>code
  code: ({ className, children, ...props }) => {
    const isBlock = /language-/.test(className || "");
    if (isBlock) {
      return (
        <code
          className={`${className || ""} block overflow-x-auto`}
          {...props}
        >
          {children}
        </code>
      );
    }
    return (
      <code
        className="rounded bg-slate-100 px-1 py-0.5 text-[11px] text-rose-600"
        {...props}
      >
        {children}
      </code>
    );
  },
  pre: ({ children }) => (
    <pre className="my-2 overflow-x-auto rounded bg-slate-900 p-2.5 text-[11px] leading-relaxed text-slate-100">
      {children}
    </pre>
  ),
  a: ({ children, href }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="text-blue-600 underline underline-offset-2 hover:text-blue-700"
    >
      {children}
    </a>
  ),
  ul: ({ children }) => (
    <ul className="my-1.5 list-disc pl-5 space-y-0.5">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="my-1.5 list-decimal pl-5 space-y-0.5">{children}</ol>
  ),
  h1: ({ children }) => (
    <h1 className="mt-2 mb-1 text-[14px] font-semibold">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="mt-2 mb-1 text-[13px] font-semibold">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="mt-1.5 mb-0.5 text-[12px] font-semibold">{children}</h3>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-1.5 border-l-2 border-slate-300 pl-2.5 text-slate-500">
      {children}
    </blockquote>
  ),
  p: ({ children }) => <p className="my-1 leading-relaxed">{children}</p>,
};

export function MarkdownMessage({ content }: { content: string }) {
  return (
    <div className="prose prose-sm prose-slate max-w-none prose-p:my-1 prose-headings:my-1">
      <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
