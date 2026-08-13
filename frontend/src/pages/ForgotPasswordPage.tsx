// 忘记密码页
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { authApi } from "@/api/auth";
import { Mail, ArrowLeft, CheckCircle2, AlertCircle } from "lucide-react";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    setLoading(true);
    try {
      await authApi.forgotPassword(email);
      setSent(true);
    } catch (e: unknown) {
      setErr((e as Error).message || "发送失败");
    } finally {
      setLoading(false);
    }
  };

  if (sent) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
        <div className="w-full max-w-sm rounded-md border border-slate-200 bg-white p-6 shadow-sm text-center">
          <CheckCircle2 className="w-10 h-10 text-green-500 mx-auto mb-2" />
          <div className="text-[14px] font-semibold text-slate-800 mb-1">邮件已发送</div>
          <p className="text-[12px] text-slate-500">
            如果 <span className="text-slate-700">{email}</span> 已注册，
            重置链接已发送到该邮箱。链接 30 分钟内有效。
          </p>
          <Link
            to="/login"
            className="mt-4 inline-flex items-center gap-1 text-[12px] text-blue-600 hover:underline"
          >
            <ArrowLeft className="w-3 h-3" /> 返回登录
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm rounded-md border border-slate-200 bg-white p-6 shadow-sm"
      >
        <h1 className="text-[15px] font-semibold text-slate-800 mb-1">忘记密码</h1>
        <p className="text-[12px] text-slate-500 mb-4">
          输入注册邮箱，我们会发送重置链接到您邮箱。
        </p>
        {err && (
          <div className="mb-3 flex items-start gap-1.5 rounded bg-red-50 border border-red-200 px-2.5 py-1.5 text-[12px] text-red-700">
            <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" /> {err}
          </div>
        )}
        <label className="block mb-3">
          <div className="text-[11px] text-slate-500 mb-1">邮箱</div>
          <div className="relative">
            <Mail className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
              className="w-full rounded border border-slate-300 pl-7 pr-2.5 py-1.5 text-[13px] focus:border-blue-500 focus:outline-none"
            />
          </div>
        </label>
        <button
          type="submit"
          disabled={loading || !email}
          className="w-full flex items-center justify-center gap-1.5 rounded bg-blue-600 text-white text-[13px] py-2 hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "发送中…" : "发送重置链接"}
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
