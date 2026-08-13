// 管理员：用户管理
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { usersApi, rolesApi, type UserInfo, type Role } from "@/api/auth";
import { Plus, Trash2, KeyRound, ToggleLeft, ToggleRight, X, ShieldCheck, ShieldOff } from "lucide-react";

export default function UsersAdminPage() {
  const qc = useQueryClient();
  const { data: users = [] } = useQuery({ queryKey: ["admin-users"], queryFn: () => usersApi.list() });
  const { data: roles = [] } = useQuery({ queryKey: ["admin-roles"], queryFn: () => rolesApi.list() });
  const [showCreate, setShowCreate] = useState(false);
  const [editingUser, setEditingUser] = useState<UserInfo | null>(null);
  const [resettingUser, setResettingUser] = useState<UserInfo | null>(null);

  const del = useMutation({
    mutationFn: (id: number) => usersApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }),
  });

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
            {users.map((u) => (
              <tr key={u.id} className="border-t border-slate-100 hover:bg-slate-50/50">
                <td className="px-3 py-2 text-slate-500">{u.id}</td>
                <td className="px-3 py-2 font-medium text-slate-800">
                  {u.username}
                  {u.is_admin && <span className="ml-1 text-[10px] text-blue-600">(admin)</span>}
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
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded ${
                      u.is_active ? "bg-green-100 text-green-700" : "bg-slate-200 text-slate-500"
                    }`}
                  >
                    {u.is_active ? "启用" : "禁用"}
                  </span>
                  {u.must_change_password && (
                    <span className="ml-1 text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">
                      强制改密
                    </span>
                  )}
                </td>
                <td className="px-3 py-2 text-slate-400 text-[11px]">
                  {u.last_login_at ? new Date(u.last_login_at).toLocaleString("zh-CN", { hour12: false }) : "—"}
                </td>
                <td className="px-3 py-2 text-right space-x-1">
                  <button
                    onClick={() => setEditingUser(u)}
                    className="text-blue-600 hover:underline text-[11px]"
                    title="编辑角色 / 状态"
                  >
                    编辑
                  </button>
                  <button
                    onClick={() => setResettingUser(u)}
                    className="text-amber-600 hover:underline text-[11px]"
                    title="重置密码"
                  >
                    重置密码
                  </button>
                  <button
                    onClick={() => {
                      if (confirm(`确定删除用户 ${u.username} 吗？`)) del.mutate(u.id);
                    }}
                    className="text-red-600 hover:underline text-[11px]"
                  >
                    <Trash2 className="w-3 h-3 inline" />
                  </button>
                </td>
              </tr>
            ))}
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
    </div>
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
    setSaving(true);
    try {
      await usersApi.create({ username, email, password, is_admin: isAdmin, role_ids: roleIds });
      onCreated();
    } catch (e: unknown) {
      setErr((e as Error).message);
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
  const [isActive, setIsActive] = useState(user.is_active);
  const [roleIds, setRoleIds] = useState<number[]>(user.roles.map((r) => r.id));
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async () => {
    setSaving(true);
    setErr(null);
    try {
      await usersApi.update(user.id, { is_active: isActive, role_ids: roleIds });
      onSaved();
    } catch (e: unknown) {
      setErr((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal title={`编辑用户：${user.username}`} onClose={onClose}>
      {err && <div className="text-[12px] text-red-600 mb-2">{err}</div>}
      <div className="mb-2 text-[12px] text-slate-600">
        邮箱：<span className="text-slate-800">{user.email}</span>
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
      setErr((e as Error).message);
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
