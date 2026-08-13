import axios from "axios";
import { getAccessToken, getRefreshToken, clearTokens } from "@/contexts/AuthContext";

const client = axios.create({
  baseURL: "/api",
  timeout: 30_000,
});

// 自动附加 Bearer token
client.interceptors.request.use((cfg) => {
  const t = getAccessToken();
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

// 401 → 自动 refresh 重试一次；refresh 也失败才登出
let isRefreshing = false;
let pendingQueue: Array<(token: string | null) => void> = [];

function processQueue(token: string | null) {
  pendingQueue.forEach((cb) => cb(token));
  pendingQueue = [];
}

client.interceptors.response.use(
  (r) => r,
  async (err) => {
    const original = err.config;
    if (err.response?.status === 401 && !original._retry) {
      const refreshToken = getRefreshToken();
      if (!refreshToken) {
        clearTokens();
        // 跳转到登录页（事件式）
        if (window.location.pathname !== "/login") {
          window.location.href = "/login";
        }
      } else if (!isRefreshing) {
        isRefreshing = true;
        original._retry = true;
        try {
          const resp = await axios.post("/api/auth/refresh", { refresh_token: refreshToken });
          localStorage.setItem("access_token", resp.data.access_token);
          localStorage.setItem("refresh_token", resp.data.refresh_token);
          processQueue(resp.data.access_token);
          original.headers.Authorization = `Bearer ${resp.data.access_token}`;
          return client(original);
        } catch (e) {
          processQueue(null);
          clearTokens();
          if (window.location.pathname !== "/login") {
            window.location.href = "/login";
          }
          return Promise.reject(e);
        } finally {
          isRefreshing = false;
        }
      } else {
        // 正在 refresh 中，排队
        return new Promise((resolve, reject) => {
          pendingQueue.push((token) => {
            if (!token) reject(err);
            else {
              original.headers.Authorization = `Bearer ${token}`;
              resolve(client(original));
            }
          });
        });
      }
    }
    const msg =
      err.response?.data?.detail ||
      err.response?.data?.message ||
      err.message ||
      "请求失败";
    return Promise.reject(new Error(typeof msg === "string" ? msg : JSON.stringify(msg)));
  }
);

export default client;
