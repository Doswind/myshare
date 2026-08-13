import axios from "axios";

const client = axios.create({
  baseURL: "/api",
  timeout: 30_000,
});

client.interceptors.response.use(
  (r) => r,
  (err) => {
    const msg =
      err.response?.data?.detail ||
      err.response?.data?.message ||
      err.message ||
      "请求失败";
    return Promise.reject(new Error(msg));
  }
);

export default client;
