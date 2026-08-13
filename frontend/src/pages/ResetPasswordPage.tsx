// 重置密码页（从邮件链接跳过来）
import { useState, type FormEvent } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { authApi } from "@/api/auth";
import { KeyRound, ArrowLeft, AlertCircle, CheckCircle2 } from "lucide-react";

export default function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const nav = useNavigate();

  const [newPw, setNewPw] = useState("");
  const [newPw2, setNewPw2] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (newPw.length < 8) return setErr("新密码至少 8 位");
    if (newPw !== newPw2) return setErr("两次输入的密码不一致");
    setLoading(true);
    try {
      await authApi.resetPassword(token, newPw);
      setDone(true);
      setTimeout(() => nav("/login"), 2000);
    } catch (e: unknown) {
      setErr((e as Error).message || "重置失败");
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
        <div className="w-full max-w-sm rounded-md border border-slate-200 bg-white p-6 text-center">
          <div className="text-[14px] text-slate-700 mb-2">链接无效</div>
          <Link to="/forgot-password" className="text-[12px] text-blue-600 hover:underline">
            重新申请重置链接
          </Link>
        </div>
      </div>
    );
  }

  if (done) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
        <div className="w-full max-w-sm rounded-md border border-slate-200 bg-white p-6 text-center">
          <CheckCircle2 className="w-10 h-10 text-green-500 mx-auto mb-2" />
          <div className="text-[14px] font-semibold text-slate-800 mb-1">密码已重置</div>
          <p className="text-[12px] text-slate-500">即将跳转到登录页…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
      <form onSubmit={onSubmit} className="w-full max-w-sm rounded-md border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-[15px] font-semibold text-slate-800 mb-1">重置密码</h1>
        <p className="text-[12px] text-slate-500 mb-4">请设置新密码（至少 8 位）。</p>
        {err && (
          <div className="mb-3 flex items-start gap-1.5 rounded bg-red-50 border border-red-200 px-2.5 py-1.5 text-[12px] text-red-700">
            <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" /> {err}
          </div>
        )}
        <Field label="新密码" type="password" value={newPw} onChange={setNewPw} autoFocus />
        <Field label="确认新密码" type="password" value={newPw2} onChange={setNewPw2} />
        <button
          type="submit"
          disabled={loading}
          className="mt-4 w-full flex items-center justify-center gap-1.5 rounded bg-blue-600 text-white text-[13px] py-2 hover:bg-blue-700 disabled:opacity-50"
        >
          <KeyRound className="w-3.5 h-3.5" /> {loading ? "重置中…" : "重置密码"}
        </button>
        <Link
          to="/login"
          className="mt-3 inline-flex items-center gap-1 text-[11px] text-slate-500 hover:text-slate-800"
        >
          <ArrowLeft className="w-3 h-3" /> 返回登录
        </Link>
      </form>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  autoFocus,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  autoFocus?: boolean;
}) {
  return (
    <label className="block mb-2.5">
      <div className="text-[11px] text-slate-500 mb-1">{label}</div>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoFocus={autoFocus}
        required
        className="w-full rounded border border-slate-300 px-2.5 py-1.5 text-[13px] focus:border-blue-500 focus:outline-none"
      />
    </label>
  );
}
