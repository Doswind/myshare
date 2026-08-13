// 管理员：角色 + 权限矩阵
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { rolesApi, permissionsApi, type Role, type Permission } from "@/api/auth";
import { Plus, X, Lock } from "lucide-react";

export default function RolesAdminPage() {
  const qc = useQueryClient();
  const { data: roles = [] } = useQuery({ queryKey: ["admin-roles"], queryFn: () => rolesApi.list() });
  const { data: permMap = {} } = useQuery({ queryKey: ["admin-perms"], queryFn: () => permissionsApi.list() });
  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState<Role | null>(null);

  const del = useMutation({
    mutationFn: (id: number) => rolesApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-roles"] }),
  });

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-[14px] font-semibold text-slate-800">角色 / 权限</h2>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1 rounded bg-blue-600 text-white text-[12px] px-2.5 py-1.5 hover:bg-blue-700"
        >
          <Plus className="w-3.5 h-3.5" /> 新建角色
        </button>
      </div>

      {/* 权限矩阵 */}
      <div className="rounded-md border border-slate-200 bg-white overflow-x-auto">
        <table className="w-full text-[11px]">
          <thead className="bg-slate-50 text-slate-500">
            <tr>
              <th className="text-left px-3 py-2 font-medium sticky left-0 bg-slate-50 z-10">权限 \ 角色</th>
              {roles.map((r) => (
                <th key={r.id} className="text-center px-3 py-2 font-medium whitespace-nowrap">
                  {r.name}
                  <div className="text-[9px] text-slate-400 font-normal">{r.code}</div>
                </th>
              ))}
              <th className="text-center px-3 py-2 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(permMap).map(([resource, perms]) => (
              <>
                <tr key={`h-${resource}`} className="bg-slate-50/50">
                  <td colSpan={roles.length + 2} className="px-3 py-1 text-[10px] text-slate-500 font-medium">
                    {resource}
                  </td>
                </tr>
                {perms.map((p) => (
                  <tr key={p.id} className="border-t border-slate-100">
                    <td className="px-3 py-1.5 text-slate-700 sticky left-0 bg-white z-10">
                      <div className="flex items-center gap-1.5">
                        <span>{p.name}</span>
                        <code className="text-[9px] text-slate-400">{p.code}</code>
                      </div>
                    </td>
                    {roles.map((r) => {
                      const has = r.permissions.some((rp) => rp.id === p.id);
                      return (
                        <td key={r.id} className="text-center px-3 py-1.5">
                          {has ? <span className="text-green-600 text-[14px]">✓</span> : <span className="text-slate-300">·</span>}
                        </td>
                      );
                    })}
                    <td className="px-3 py-1.5 text-center"></td>
                  </tr>
                ))}
              </>
            ))}
          </tbody>
        </table>
      </div>

      {/* 角色列表（操作） */}
      <div className="rounded-md border border-slate-200 bg-white overflow-hidden">
        <div className="px-3 py-2 text-[12px] font-medium text-slate-700 bg-slate-50 border-b border-slate-200">
          角色管理
        </div>
        <table className="w-full text-[12px]">
          <thead className="text-slate-500">
            <tr>
              <th className="text-left px-3 py-1.5 font-medium">代码</th>
              <th className="text-left px-3 py-1.5 font-medium">名称</th>
              <th className="text-left px-3 py-1.5 font-medium">说明</th>
              <th className="text-left px-3 py-1.5 font-medium">状态</th>
              <th className="text-right px-3 py-1.5 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {roles.map((r) => (
              <tr key={r.id} className="border-t border-slate-100">
                <td className="px-3 py-1.5">
                  <code className="text-[10px] text-slate-600">{r.code}</code>
                  {r.is_builtin && <Lock className="w-3 h-3 inline ml-1 text-slate-400" />}
                </td>
                <td className="px-3 py-1.5 font-medium text-slate-800">{r.name}</td>
                <td className="px-3 py-1.5 text-slate-500">{r.description}</td>
                <td className="px-3 py-1.5">
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded ${
                      r.is_active ? "bg-green-100 text-green-700" : "bg-slate-200 text-slate-500"
                    }`}
                  >
                    {r.is_active ? "启用" : "禁用"}
                  </span>
                </td>
                <td className="px-3 py-1.5 text-right space-x-2">
                  <button onClick={() => setEditing(r)} className="text-blue-600 hover:underline text-[11px]">
                    编辑
                  </button>
                  {!r.is_builtin && (
                    <button
                      onClick={() => {
                        if (confirm(`确定删除角色 ${r.name} 吗？`)) del.mutate(r.id);
                      }}
                      className="text-red-600 hover:underline text-[11px]"
                    >
                      删除
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showCreate && (
        <RoleModal
          permMap={permMap}
          onClose={() => setShowCreate(false)}
          onSaved={() => {
            setShowCreate(false);
            qc.invalidateQueries({ queryKey: ["admin-roles"] });
          }}
        />
      )}
      {editing && (
        <RoleModal
          role={editing}
          permMap={permMap}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            qc.invalidateQueries({ queryKey: ["admin-roles"] });
          }}
        />
      )}
    </div>
  );
}

function RoleModal({
  role,
  permMap,
  onClose,
  onSaved,
}: {
  role?: Role;
  permMap: Record<string, Permission[]>;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = !!role;
  const [code, setCode] = useState(role?.code || "");
  const [name, setName] = useState(role?.name || "");
  const [description, setDescription] = useState(role?.description || "");
  const [isActive, setIsActive] = useState(role?.is_active ?? true);
  const [permIds, setPermIds] = useState<number[]>(role?.permissions.map((p) => p.id) || []);
  const [err, setErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const togglePerm = (id: number) =>
    setPermIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  const submit = async () => {
    setErr(null);
    setSaving(true);
    try {
      if (isEdit) {
        await rolesApi.update(role!.id, { name, description, is_active: isActive, permission_ids: permIds });
      } else {
        await rolesApi.create({ code, name, description, permission_ids: permIds });
      }
      onSaved();
    } catch (e: unknown) {
      setErr((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-[1px] p-4" onClick={onClose}>
      <div className="w-full max-w-lg max-h-[90vh] overflow-auto rounded-md border border-slate-200 bg-white shadow-lg" onClick={(e) => e.stopPropagation()}>
        <div className="sticky top-0 flex items-center justify-between px-4 py-2.5 border-b border-slate-200 bg-white">
          <h3 className="text-[13px] font-semibold text-slate-800">{isEdit ? `编辑角色：${role!.name}` : "新建角色"}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="p-4 space-y-3">
          {err && <div className="text-[12px] text-red-600">{err}</div>}
          <div className="grid grid-cols-2 gap-2">
            <Input label="代码（英文，唯一）" value={code} onChange={setCode} disabled={isEdit} />
            <Input label="名称" value={name} onChange={setName} />
          </div>
          <label className="block">
            <div className="text-[11px] text-slate-500 mb-1">说明</div>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full rounded border border-slate-300 px-2.5 py-1.5 text-[13px] focus:border-blue-500 focus:outline-none"
            />
          </label>
          {isEdit && (
            <label className="flex items-center gap-1.5 text-[12px] cursor-pointer">
              <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
              启用
            </label>
          )}

          <div>
            <div className="text-[11px] text-slate-500 mb-1.5">分配权限（{permIds.length} 个）</div>
            <div className="rounded border border-slate-200 max-h-72 overflow-y-auto">
              {Object.entries(permMap).map(([res, perms]) => (
                <div key={res} className="border-b border-slate-100 last:border-0">
                  <div className="bg-slate-50 px-2 py-1 text-[10px] font-medium text-slate-500 sticky top-0">
                    {res}
                  </div>
                  <div className="p-2 grid grid-cols-2 gap-1">
                    {perms.map((p) => (
                      <label key={p.id} className="flex items-center gap-1.5 text-[11px] cursor-pointer">
                        <input
                          type="checkbox"
                          checked={permIds.includes(p.id)}
                          onChange={() => togglePerm(p.id)}
                        />
                        {p.name}
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-2">
            <button onClick={onClose} className="text-[12px] px-3 py-1.5 rounded border border-slate-300 hover:bg-slate-50">
              取消
            </button>
            <button
              onClick={submit}
              disabled={saving || !code || !name}
              className="text-[12px] px-3 py-1.5 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? "保存中…" : "保存"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Input({
  label,
  value,
  onChange,
  disabled,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
}) {
  return (
    <label className="block">
      <div className="text-[11px] text-slate-500 mb-1">{label}</div>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="w-full rounded border border-slate-300 px-2.5 py-1.5 text-[13px] focus:border-blue-500 focus:outline-none disabled:bg-slate-50"
      />
    </label>
  );
}
