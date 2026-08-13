// 认证 API 封装（login / me / forgot / reset / change）
import client from "./client";

export interface Permission {
  id: number;
  code: string;
  name: string;
  resource: string;
  action: string;
  description: string;
}

export interface Role {
  id: number;
  code: string;
  name: string;
  description: string;
  is_builtin: boolean;
  is_active: boolean;
  permissions: Permission[];
}

export interface UserInfo {
  id: number;
  username: string;
  email: string;
  is_active: boolean;
  is_admin: boolean;
  must_change_password: boolean;
  roles: Role[];
  profile?: { display_name: string; phone: string; avatar: string };
  created_at: string;
  last_login_at: string;
}

export interface LoginResp {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: UserInfo;
}

export const authApi = {
  login: (username: string, password: string) =>
    client.post<LoginResp>("/auth/login", { username, password }).then((r) => r.data),

  refresh: (refresh_token: string) =>
    client.post<LoginResp>("/auth/refresh", { refresh_token }).then((r) => r.data),

  logout: () => client.post("/auth/logout").then((r) => r.data),

  me: () => client.get<UserInfo>("/auth/me").then((r) => r.data),

  changePassword: (old_password: string, new_password: string) =>
    client.post("/auth/change-password", { old_password, new_password }).then((r) => r.data),

  forgotPassword: (email: string) =>
    client.post<{ ok: boolean; message: string }>("/auth/forgot-password", { email }).then((r) => r.data),

  resetPassword: (token: string, new_password: string) =>
    client.post<{ ok: boolean }>("/auth/reset-password", { token, new_password }).then((r) => r.data),

  updateProfile: (data: { display_name: string; phone: string; avatar: string }) =>
    client.patch<UserInfo>("/users/me", data).then((r) => r.data),
};

export const usersApi = {
  list: () => client.get<UserInfo[]>("/users").then((r) => r.data),
  create: (data: {
    username: string;
    email: string;
    password: string;
    is_admin?: boolean;
    role_ids?: number[];
  }) => client.post<UserInfo>("/users", data).then((r) => r.data),
  update: (
    id: number,
    data: { email?: string; is_active?: boolean; role_ids?: number[] }
  ) => client.patch<UserInfo>(`/users/${id}`, data).then((r) => r.data),
  remove: (id: number) => client.delete<{ ok: boolean }>(`/users/${id}`).then((r) => r.data),
  resetPassword: (id: number, new_password: string) =>
    client.post<{ ok: boolean; new_password: string }>(`/users/${id}/reset-password`, {
      new_password,
    }).then((r) => r.data),
};

export const rolesApi = {
  list: () => client.get<Role[]>("/roles").then((r) => r.data),
  create: (data: { code: string; name: string; description: string; permission_ids: number[] }) =>
    client.post<Role>("/roles", data).then((r) => r.data),
  update: (
    id: number,
    data: { name?: string; description?: string; is_active?: boolean; permission_ids?: number[] }
  ) => client.patch<Role>(`/roles/${id}`, data).then((r) => r.data),
  remove: (id: number) => client.delete<{ ok: boolean }>(`/roles/${id}`).then((r) => r.data),
};

export const permissionsApi = {
  list: () =>
    client.get<Record<string, Permission[]>>("/permissions").then((r) => r.data),
};
