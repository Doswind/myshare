// 登录页
import { useState, type FormEvent } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { authApi } from "@/api/auth";
import { LogIn, AlertCircle } from "lucide-react";

export default function LoginPage() {
  const { login, user, updateUser } = useAuth();
  const nav = useNavigate();
  // 登录后默认进入持仓看板（无论普通用户还是管理员）
  const HOME = "/";

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  // 强制改密：登录成功后用户必须先改密
  const [forcing, setForcing] = useState(false);
  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [newPw2, setNewPw2] = useState("");

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    setLoading(true);
    try {
      const u = await login(username, password);
      if (u.must_change_password) {
        setForcing(true);
        setOldPw(password);
      } else {
        nav(HOME, { replace: true });
      }
    } catch (e: unknown) {
      setErr((e as Error).message || "登录失败");
    } finally {
      setLoading(false);
    }
  };

  const onChangePw = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (newPw.length < 8) {
      setErr("新密码至少 8 位");
      return;
    }
    if (newPw !== newPw2) {
      setErr("两次输入的新密码不一致");
      return;
    }
    setLoading(true);
    try {
      await authApi.changePassword(oldPw, newPw);
      // 刷新 user 信息
      if (user) updateUser({ ...user, must_change_password: false });
      nav(HOME, { replace: true });
    } catch (e: unknown) {
      setErr((e as Error).message || "改密失败");
    } finally {
      setLoading(false);
    }
  };

  if (forcing) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
        <form
          onSubmit={onChangePw}
          className="w-full max-w-sm rounded-md border border-slate-200 bg-white p-6 shadow-sm"
        >
          <div className="text-[15px] font-semibold text-slate-800 mb-1">首次登录需修改密码</div>
          <p className="text-[12px] text-slate-500 mb-4">为了您的账户安全，请设置新密码后继续。</p>
          {err && (
            <div className="mb-3 flex items-start gap-1.5 rounded bg-red-50 border border-red-200 px-2.5 py-1.5 text-[12px] text-red-700">
              <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" /> {err}
            </div>
          )}
          <Field label="新密码（至少 8 位）" type="password" value={newPw} onChange={setNewPw} autoFocus />
          <Field label="确认新密码" type="password" value={newPw2} onChange={setNewPw2} />
          <button
            type="submit"
            disabled={loading}
            className="mt-4 w-full flex items-center justify-center gap-1.5 rounded bg-blue-600 text-white text-[13px] py-2 hover:bg-blue-700 disabled:opacity-50"
          >
            <LogIn className="w-3.5 h-3.5" /> 确认并登录
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm rounded-md border border-slate-200 bg-white p-6 shadow-sm"
      >
        <div className="flex items-center gap-2 mb-1">
          <div className="w-8 h-8 rounded bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center text-white text-[14px] font-bold">
            F
          </div>
          <div>
            <div className="text-[15px] font-semibold text-slate-800">Fund Analyzer</div>
            <div className="text-[10px] text-slate-400">主力基金持仓分析</div>
          </div>
        </div>
        <p className="text-[12px] text-slate-500 mt-3 mb-4">请登录以继续</p>

        {err && (
          <div className="mb-3 flex items-start gap-1.5 rounded bg-red-50 border border-red-200 px-2.5 py-1.5 text-[12px] text-red-700">
            <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" /> {err}
          </div>
        )}

        <Field label="用户名" value={username} onChange={setUsername} autoFocus />
        <Field label="密码" type="password" value={password} onChange={setPassword} />

        <button
          type="submit"
          disabled={loading || !username || !password}
          className="mt-4 w-full flex items-center justify-center gap-1.5 rounded bg-blue-600 text-white text-[13px] py-2 hover:bg-blue-700 disabled:opacity-50"
        >
          <LogIn className="w-3.5 h-3.5" /> {loading ? "登录中…" : "登录"}
        </button>

        <div className="mt-3 flex items-center justify-between text-[11px]">
          <Link to="/forgot-password" className="text-blue-600 hover:underline">
            忘记密码？
          </Link>
          <span className="text-slate-400">v0.1.0</span>
        </div>
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
