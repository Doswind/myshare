// 管理员：用户管理
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { usersApi, rolesApi, type UserInfo, type Role } from "@/api/auth";
import { useAuth } from "@/contexts/AuthContext";
import { ConfirmDialog, type ConfirmOptions } from "@/components/common/ConfirmDialog";
import { Plus, Trash2, X } from "lucide-react";

export default function UsersAdminPage() {
  const qc = useQueryClient();
  const { user: currentUser } = useAuth();
  const { data: users = [] } = useQuery({ queryKey: ["admin-users"], queryFn: () => usersApi.list() });
  const { data: roles = [] } = useQuery({ queryKey: ["admin-roles"], queryFn: () => rolesApi.list() });
  const [showCreate, setShowCreate] = useState(false);
  const [editingUser, setEditingUser] = useState<UserInfo | null>(null);
  const [resettingUser, setResettingUser] = useState<UserInfo | null>(null);
  const [confirm, setConfirm] = useState<(ConfirmOptions & { onOk: () => void }) | null>(null);

  const del = useMutation({
    mutationFn: (id: number) => usersApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  const toggleActive = useMutation({
    mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) =>
      usersApi.update(id, { is_active }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      const u = users.find((x) => x.id === vars.id);
      showToast("ok", `已${vars.is_active ? "启用" : "禁用"}：${u?.username || ""}`);
    },
    onError: (e: any) => showToast("err", formatErr(e)),
  });

  const [toast, setToast] = useState<{ type: "ok" | "err"; msg: string } | null>(null);
  const showToast = (type: "ok" | "err", msg: string) => {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 3000);
  };

  // 触发切换启用的确认弹窗
  const askToggle = (u: UserInfo) => {
    if (u.id === currentUser?.id) {
      showToast("err", "不能禁用自己的账号");
      return;
    }
    const willEnable = !u.is_active;
    setConfirm({
      title: willEnable ? `启用用户「${u.username}」` : `禁用用户「${u.username}」`,
      description: willEnable
        ? "启用后该用户将可以正常登录系统。"
        : "禁用后该用户将无法登录，所有会话会失效。",
      confirmText: willEnable ? "启用" : "禁用",
      variant: willEnable ? "info" : "warning",
      onOk: () => {
        toggleActive.mutate({ id: u.id, is_active: willEnable });
        setConfirm(null);
      },
    });
  };

  // 触发删除的确认弹窗
  const askDelete = (u: UserInfo) => {
    if (u.id === currentUser?.id) {
      showToast("err", "不能删除自己的账号");
      return;
    }
    setConfirm({
      title: `删除用户「${u.username}」`,
      description: "此操作不可恢复。用户的所有数据（自选股、登录记录等）将一并清除。",
      confirmText: "删除",
      variant: "danger",
      onOk: () => {
        del.mutate(u.id);
        setConfirm(null);
      },
    });
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-[14px] font-semibold text-slate-800">用户管理</h2>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1 rounded bg-blue-600 text-white text-[12px] px-2.5 py-1.5 hover:bg-blue-700"
        >
          <Plus className="w-3.5 h-3.5" /> 新增用户
        </button>
      </div>

      <div className="rounded-md border border-slate-200 bg-white overflow-hidden">
        <table className="w-full text-[12px]">
          <thead className="bg-slate-50 text-slate-500">
            <tr>
              <th className="text-left px-3 py-2 font-medium">ID</th>
              <th className="text-left px-3 py-2 font-medium">用户名</th>
              <th className="text-left px-3 py-2 font-medium">邮箱</th>
              <th className="text-left px-3 py-2 font-medium">角色</th>
              <th className="text-left px-3 py-2 font-medium">状态</th>
              <th className="text-left px-3 py-2 font-medium">最后登录</th>
              <th className="text-right px-3 py-2 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => {
              const isSelf = u.id === currentUser?.id;
              return (
                <tr key={u.id} className="border-t border-slate-100 hover:bg-slate-50/50">
                  <td className="px-3 py-2 text-slate-500">{u.id}</td>
                  <td className="px-3 py-2 font-medium text-slate-800">
                    {u.username}
                    {u.is_admin && <span className="ml-1 text-[10px] text-blue-600">(admin)</span>}
                    {isSelf && <span className="ml-1 text-[10px] text-emerald-600">(你)</span>}
                  </td>
                  <td className="px-3 py-2 text-slate-600">{u.email}</td>
                  <td className="px-3 py-2">
                    {u.roles.map((r) => (
                      <span
                        key={r.id}
                        className="inline-block rounded bg-slate-100 text-slate-700 text-[10px] px-1.5 py-0.5 mr-1"
                      >
                        {r.name}
                      </span>
                    ))}
                  </td>
                  <td className="px-3 py-2">
                    <Switch
                      checked={u.is_active}
                      disabled={isSelf || toggleActive.isPending}
                      onChange={() => askToggle(u)}
                      label={u.is_active ? "启用" : "禁用"}
                    />
                  </td>
                  <td className="px-3 py-2 text-slate-400 text-[11px]">
                    {u.last_login_at ? new Date(u.last_login_at).toLocaleString("zh-CN", { hour12: false }) : "—"}
                  </td>
                  <td className="px-3 py-2 text-right space-x-1 whitespace-nowrap">
                    <button
                      onClick={() => setEditingUser(u)}
                      disabled={isSelf}
                      className="text-blue-600 hover:underline text-[11px] disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:no-underline"
                      title={isSelf ? "请到个人中心修改自己的信息" : "编辑角色 / 邮箱"}
                    >
                      编辑
                    </button>
                    <button
                      onClick={() => setResettingUser(u)}
                      disabled={isSelf}
                      className="text-amber-600 hover:underline text-[11px] disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:no-underline"
                      title={isSelf ? "请到个人中心修改自己的密码" : "重置密码"}
                    >
                      重置密码
                    </button>
                    <button
                      onClick={() => askDelete(u)}
                      disabled={isSelf}
                      className="text-red-600 hover:underline text-[11px] disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:no-underline"
                      title={isSelf ? "不能删除自己" : "删除用户"}
                    >
                      <Trash2 className="w-3 h-3 inline" />
                    </button>
                  </td>
                </tr>
              );
            })}
            {users.length === 0 && (
              <tr>
                <td colSpan={7} className="text-center py-6 text-slate-400 text-[12px]">
                  暂无用户
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {showCreate && (
        <CreateUserModal
          roles={roles}
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false);
            qc.invalidateQueries({ queryKey: ["admin-users"] });
          }}
        />
      )}
      {editingUser && (
        <EditUserModal
          user={editingUser}
          roles={roles}
          onClose={() => setEditingUser(null)}
          onSaved={() => {
            setEditingUser(null);
            qc.invalidateQueries({ queryKey: ["admin-users"] });
          }}
        />
      )}
      {resettingUser && (
        <ResetPwModal
          user={resettingUser}
          onClose={() => setResettingUser(null)}
          onReset={() => setResettingUser(null)}
        />
      )}

      {confirm && (
        <ConfirmDialog
          open
          title={confirm.title}
          description={confirm.description}
          confirmText={confirm.confirmText}
          cancelText={confirm.cancelText}
          variant={confirm.variant}
          onConfirm={confirm.onOk}
          onCancel={() => setConfirm(null)}
        />
      )}

      {toast && (
        <div
          className={`fixed bottom-4 right-4 z-50 px-3 py-2 rounded shadow text-[12px] ${
            toast.type === "ok" ? "bg-emerald-600 text-white" : "bg-red-600 text-white"
          }`}
        >
          {toast.msg}
        </div>
      )}
    </div>
  );
}

// iOS 风开关（绿色=启用，灰=禁用）
function Switch({
  checked,
  disabled,
  onChange,
  label,
}: {
  checked: boolean;
  disabled?: boolean;
  onChange: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={onChange}
      title={label}
      className={`relative inline-flex items-center h-[18px] w-8 rounded-full transition-colors duration-200
        ${checked ? "bg-emerald-500" : "bg-slate-300"}
        ${disabled ? "opacity-40 cursor-not-allowed" : "cursor-pointer hover:brightness-110"}`}
    >
      <span
        className={`absolute top-[2px] left-[2px] w-[14px] h-[14px] rounded-full bg-white shadow transition-transform duration-200
          ${checked ? "translate-x-[14px]" : "translate-x-0"}`}
      />
    </button>
  );
}

function CreateUserModal({ roles, onClose, onCreated }: { roles: Role[]; onClose: () => void; onCreated: () => void }) {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [roleIds, setRoleIds] = useState<number[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    setErr(null);
    // 前端先校验邮箱格式，避免无效请求
    if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setErr("邮箱格式不正确，请输入有效的邮箱地址");
      return;
    }
    setSaving(true);
    try {
      await usersApi.create({ username, email, password, is_admin: isAdmin, role_ids: roleIds });
      onCreated();
    } catch (e: unknown) {
      setErr(formatErr(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal title="新增用户" onClose={onClose}>
      {err && <div className="text-[12px] text-red-600 mb-2">{err}</div>}
      <Input label="用户名" value={username} onChange={setUsername} />
      <Input label="邮箱" type="email" value={email} onChange={setEmail} />
      <Input label="初始密码（≥8 位）" type="password" value={password} onChange={setPassword} />
      <div className="mb-2">
        <label className="flex items-center gap-1.5 text-[12px] text-slate-700 cursor-pointer">
          <input type="checkbox" checked={isAdmin} onChange={(e) => setIsAdmin(e.target.checked)} />
          管理员（绕过 RBAC，拥有所有权限）
        </label>
      </div>
      <div className="mb-2">
        <div className="text-[11px] text-slate-500 mb-1">分配角色</div>
        <div className="space-y-1">
          {roles.map((r) => (
            <label key={r.id} className="flex items-center gap-1.5 text-[12px] cursor-pointer">
              <input
                type="checkbox"
                checked={roleIds.includes(r.id)}
                onChange={(e) =>
                  setRoleIds((prev) =>
                    e.target.checked ? [...prev, r.id] : prev.filter((x) => x !== r.id)
                  )
                }
              />
              {r.name} <span className="text-slate-400 text-[10px]">({r.code})</span>
            </label>
          ))}
        </div>
      </div>
      <div className="flex justify-end gap-2 mt-3">
        <button onClick={onClose} className="text-[12px] px-3 py-1.5 rounded border border-slate-300 hover:bg-slate-50">
          取消
        </button>
        <button
          onClick={submit}
          disabled={saving || !username || !email || !password}
          className="text-[12px] px-3 py-1.5 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? "创建中…" : "创建"}
        </button>
      </div>
    </Modal>
  );
}

function EditUserModal({ user, roles, onClose, onSaved }: { user: UserInfo; roles: Role[]; onClose: () => void; onSaved: () => void }) {
  const [email, setEmail] = useState(user.email);
  const [isActive, setIsActive] = useState(user.is_active);
  const [roleIds, setRoleIds] = useState<number[]>(user.roles.map((r) => r.id));
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async () => {
    setErr(null);
    // 前端先校验邮箱格式
    if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setErr("邮箱格式不正确，请输入有效的邮箱地址");
      return;
    }
    setSaving(true);
    try {
      await usersApi.update(user.id, {
        email: email !== user.email ? email : undefined,
        is_active: isActive,
        role_ids: roleIds,
      });
      onSaved();
    } catch (e: unknown) {
      setErr(formatErr(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal title={`编辑用户：${user.username}`} onClose={onClose}>
      {err && <div className="text-[12px] text-red-600 mb-2">{err}</div>}
      <div className="mb-2">
        <div className="text-[11px] text-slate-500 mb-1">邮箱</div>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded border border-slate-300 px-2.5 py-1.5 text-[13px] focus:border-blue-500 focus:outline-none"
          placeholder="user@example.com"
        />
        <div className="text-[10px] text-slate-400 mt-0.5">修改后该邮箱将用于密码重置</div>
      </div>
      <div className="mb-2">
        <label className="flex items-center gap-1.5 text-[12px] text-slate-700 cursor-pointer">
          <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
          启用
        </label>
      </div>
      <div className="mb-2">
        <div className="text-[11px] text-slate-500 mb-1">分配角色</div>
        <div className="space-y-1">
          {roles.map((r) => (
            <label key={r.id} className="flex items-center gap-1.5 text-[12px] cursor-pointer">
              <input
                type="checkbox"
                checked={roleIds.includes(r.id)}
                onChange={(e) =>
                  setRoleIds((prev) =>
                    e.target.checked ? [...prev, r.id] : prev.filter((x) => x !== r.id)
                  )
                }
              />
              {r.name} <span className="text-slate-400 text-[10px]">({r.code})</span>
            </label>
          ))}
        </div>
      </div>
      <div className="flex justify-end gap-2 mt-3">
        <button onClick={onClose} className="text-[12px] px-3 py-1.5 rounded border border-slate-300 hover:bg-slate-50">
          取消
        </button>
        <button
          onClick={submit}
          disabled={saving}
          className="text-[12px] px-3 py-1.5 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? "保存中…" : "保存"}
        </button>
      </div>
    </Modal>
  );
}

function ResetPwModal({ user, onClose, onReset }: { user: UserInfo; onClose: () => void; onReset: () => void }) {
  const [newPw, setNewPw] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  const submit = async () => {
    setSaving(true);
    setErr(null);
    try {
      const r = await usersApi.resetPassword(user.id, newPw);
      setResult(r.new_password);
    } catch (e: unknown) {
      setErr(formatErr(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal title={`重置密码：${user.username}`} onClose={onClose}>
      {result ? (
        <div className="space-y-2">
          <div className="text-[12px] text-slate-600">新密码已生成（用户首次登录会强制改密）：</div>
          <div className="rounded bg-amber-50 border border-amber-200 p-2 text-[14px] font-mono text-amber-900">
            {result}
          </div>
          <div className="text-[11px] text-slate-400">请复制给用户</div>
          <div className="flex justify-end mt-3">
            <button onClick={onReset} className="text-[12px] px-3 py-1.5 rounded bg-blue-600 text-white hover:bg-blue-700">
              完成
            </button>
          </div>
        </div>
      ) : (
        <>
          {err && <div className="text-[12px] text-red-600 mb-2">{err}</div>}
          <Input label="新密码（≥8 位）" type="password" value={newPw} onChange={setNewPw} />
          <div className="flex justify-end gap-2 mt-3">
            <button onClick={onClose} className="text-[12px] px-3 py-1.5 rounded border border-slate-300 hover:bg-slate-50">
              取消
            </button>
            <button
              onClick={submit}
              disabled={saving || newPw.length < 8}
              className="text-[12px] px-3 py-1.5 rounded bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-50"
            >
              {saving ? "重置中…" : "重置"}
            </button>
          </div>
        </>
      )}
    </Modal>
  );
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-[1px] p-4" onClick={onClose}>
      <div
        className="w-full max-w-sm rounded-md border border-slate-200 bg-white shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-200">
          <h3 className="text-[13px] font-semibold text-slate-800">{title}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}

function Input({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
}) {
  return (
    <label className="block mb-2.5">
      <div className="text-[11px] text-slate-500 mb-1">{label}</div>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded border border-slate-300 px-2.5 py-1.5 text-[13px] focus:border-blue-500 focus:outline-none"
      />
    </label>
  );
}

// 把后端 422/400 detail（可能是字符串、对象或数组）解析为可读消息
function formatErr(e: unknown): string {
  if (!e) return "未知错误";
  if (typeof e === "string") return e;
  const a = e as any;
  // 优先取 axios response 的 detail
  const detail = a.response?.data?.detail ?? a.detail;
  if (detail) {
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length) {
      const first = detail[0];
      // 优先按字段名做中文映射
      const fieldMap: Record<string, string> = {
        email: "邮箱",
        username: "用户名",
        password: "密码",
        role_ids: "角色",
        is_active: "状态",
      };
      const rawField = first.loc?.filter((x: any) => x !== "body").pop() || "字段";
      const fieldName = fieldMap[rawField] || rawField;
      const msg = first.msg || "格式不正确";
      // 邮箱常见的英文错误翻译
      let friendlyMsg = msg;
      if (/value is not a valid email/i.test(msg)) friendlyMsg = "邮箱格式不正确";
      else if (/at least 8/i.test(msg) || /string_too_short/i.test(msg)) friendlyMsg = "长度不足 8 位";
      else if (/already/i.test(msg)) friendlyMsg = msg;
      return `${fieldName}：${friendlyMsg}`;
    }
    return JSON.stringify(detail);
  }
  if (a.message) return a.message;
  try { return JSON.stringify(e); } catch { return String(e); }
}
