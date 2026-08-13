// 个人中心：基础信息 + 改密
import { useState, type FormEvent } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { authApi } from "@/api/auth";
import { User, Phone, Camera, Save, KeyRound, AlertCircle, CheckCircle2, Mail } from "lucide-react";

export default function ProfilePage() {
  const { user, updateUser, logout } = useAuth();
  if (!user) return null;

  const [displayName, setDisplayName] = useState(user.profile?.display_name || "");
  const [phone, setPhone] = useState(user.profile?.phone || "");
  const [avatar, setAvatar] = useState(user.profile?.avatar || "");
  const [email, setEmail] = useState(user.email || "");
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileMsg, setProfileMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [newPw2, setNewPw2] = useState("");
  const [savingPw, setSavingPw] = useState(false);
  const [pwMsg, setPwMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  const saveProfile = async (e: FormEvent) => {
    e.preventDefault();
    setProfileMsg(null);
    setSavingProfile(true);
    try {
      const u = await authApi.updateProfile({
        display_name: displayName,
        phone,
        avatar,
        email: email !== user.email ? email : undefined,
      });
      updateUser(u);
      setProfileMsg({ type: "ok", text: "已保存" });
    } catch (e: unknown) {
      setProfileMsg({ type: "err", text: formatErr(e) });
    } finally {
      setSavingProfile(false);
    }
  };

  const changePw = async (e: FormEvent) => {
    e.preventDefault();
    setPwMsg(null);
    if (newPw.length < 8) return setPwMsg({ type: "err", text: "新密码至少 8 位" });
    if (newPw !== newPw2) return setPwMsg({ type: "err", text: "两次密码不一致" });
    setSavingPw(true);
    try {
      await authApi.changePassword(oldPw, newPw);
      setPwMsg({ type: "ok", text: "密码已修改，请重新登录" });
      setTimeout(() => logout(), 1500);
    } catch (e: unknown) {
      setPwMsg({ type: "err", text: formatErr(e) });
    } finally {
      setSavingPw(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-3">
      <h2 className="text-[14px] font-semibold text-slate-800">个人中心</h2>

      {/* 基础信息 */}
      <form
        onSubmit={saveProfile}
        className="rounded-md border border-slate-200 bg-white p-4 space-y-3"
      >
        <div className="flex items-center justify-between">
          <div>
            <div className="text-[13px] font-medium text-slate-800">基础信息</div>
            <div className="text-[11px] text-slate-400">仅自己和管理员可见</div>
          </div>
          <div className="text-[10px] text-slate-400">
            角色：{user.roles.map((r) => r.name).join(" / ")}
            {user.is_admin && <span className="ml-1 text-blue-600">（管理员）</span>}
          </div>
        </div>

        <Field icon={<User className="w-3.5 h-3.5" />} label="显示名" value={displayName} onChange={setDisplayName} />
        <Field icon={<Phone className="w-3.5 h-3.5" />} label="手机号" value={phone} onChange={setPhone} />
        <Field icon={<Mail className="w-3.5 h-3.5" />} label="邮箱" type="email" value={email} onChange={setEmail} />
        <Field icon={<Camera className="w-3.5 h-3.5" />} label="头像 URL" value={avatar} onChange={setAvatar} />

        {profileMsg && <Msg type={profileMsg.type} text={profileMsg.text} />}

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={savingProfile}
            className="flex items-center gap-1 rounded bg-blue-600 text-white text-[12px] px-3 py-1.5 hover:bg-blue-700 disabled:opacity-50"
          >
            <Save className="w-3.5 h-3.5" /> {savingProfile ? "保存中…" : "保存"}
          </button>
        </div>
      </form>

      {/* 改密 */}
      <form onSubmit={changePw} className="rounded-md border border-slate-200 bg-white p-4 space-y-3">
        <div>
          <div className="text-[13px] font-medium text-slate-800">修改密码</div>
          <div className="text-[11px] text-slate-400">修改后需重新登录</div>
        </div>
        <PwField label="当前密码" value={oldPw} onChange={setOldPw} />
        <PwField label="新密码（至少 8 位）" value={newPw} onChange={setNewPw} />
        <PwField label="确认新密码" value={newPw2} onChange={setNewPw2} />
        {pwMsg && <Msg type={pwMsg.type} text={pwMsg.text} />}
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={savingPw}
            className="flex items-center gap-1 rounded bg-blue-600 text-white text-[12px] px-3 py-1.5 hover:bg-blue-700 disabled:opacity-50"
          >
            <KeyRound className="w-3.5 h-3.5" /> {savingPw ? "提交中…" : "修改密码"}
          </button>
        </div>
      </form>
    </div>
  );
}

function Field({
  icon,
  label,
  value,
  onChange,
  type = "text",
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
}) {
  return (
    <label className="block">
      <div className="text-[11px] text-slate-500 mb-1">{label}</div>
      <div className="relative">
        <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400">{icon}</span>
        <input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full rounded border border-slate-300 pl-7 pr-2.5 py-1.5 text-[13px] focus:border-blue-500 focus:outline-none"
        />
      </div>
    </label>
  );
}

function PwField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="block">
      <div className="text-[11px] text-slate-500 mb-1">{label}</div>
      <input
        type="password"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded border border-slate-300 px-2.5 py-1.5 text-[13px] focus:border-blue-500 focus:outline-none"
      />
    </label>
  );
}

function Msg({ type, text }: { type: "ok" | "err"; text: string }) {
  return (
    <div
      className={`flex items-center gap-1.5 rounded px-2.5 py-1.5 text-[12px] ${
        type === "ok" ? "bg-green-50 border border-green-200 text-green-700" : "bg-red-50 border border-red-200 text-red-700"
      }`}
    >
      {type === "ok" ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertCircle className="w-3.5 h-3.5" />}
      {text}
    </div>
  );
}

function formatErr(e: unknown): string {
  if (!e) return "未知错误";
  if (typeof e === "string") return e;
  const a = e as any;
  if (a.response?.data?.detail) {
    const d = a.response.data.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d) && d.length) {
      const first = d[0];
      const field = (first.loc?.filter((x: any) => x !== "body") || []).join(".") || "字段";
      return `${field}：${first.msg || "格式不正确"}`;
    }
    return JSON.stringify(d);
  }
  if (a.message) return a.message;
  try { return JSON.stringify(e); } catch { return String(e); }
}
