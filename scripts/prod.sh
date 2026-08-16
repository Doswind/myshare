#!/usr/bin/env bash
# 生产环境启动/停止 share 项目前后端（允许互联网访问）
#
# 用法:
#   ./scripts/prod.sh start [be|fe]    启动 默认两端 可指定仅 be 或 fe
#   ./scripts/prod.sh stop [be|fe]     停止
#   ./scripts/prod.sh restart [be|fe]  重启
#   ./scripts/prod.sh status           查看状态
#   ./scripts/prod.sh logs [be|fe]     跟踪日志
#
# 与 dev.sh 的区别（生产化）:
#   - 后端 uvicorn 不带 --reload, 绑定 0.0.0.0, 单 worker
#     (单 worker 是硬性要求: AI 会话后台续跑用进程内内存, APScheduler 也只应跑一份)
#   - 前端不 build, 直接跑源码 vite dev server, 绑定 0.0.0.0 (内网自用)
#   - /api 由 vite dev server 的 server.proxy 同源代理到本机后端
#
# 环境变量:
#   BIND_HOST      监听地址 默认 0.0.0.0 (对外)
#   BACKEND_PORT   后端端口 默认 8000
#   FRONTEND_PORT  前端端口 默认 5173
#
# 安全提醒: 仅限可信内网使用; 若要暴露公网, 强烈建议前置
#   nginx/caddy 做 TLS(HTTPS) + 反向代理, 并设置强 JWT_SECRET。

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"

RUN_DIR="$ROOT/.run"
LOG_DIR="$ROOT/logs"
mkdir -p "$RUN_DIR" "$LOG_DIR"

BACKEND_PID_FILE="$RUN_DIR/prod-backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/prod-frontend.pid"
BACKEND_LOG="$LOG_DIR/prod-backend.log"
FRONTEND_LOG="$LOG_DIR/prod-frontend.log"

BIND_HOST="${BIND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

pid_alive() {
  local pid_file="$1"
  [[ -f "$pid_file" ]] || return 1
  local pid; pid="$(cat "$pid_file" 2>/dev/null || true)"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

port_in_use() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN 2>/dev/null | grep -q LISTEN
}
# PLACEHOLDER
find_python() {
  if [[ -x "$BACKEND_DIR/.venv/bin/python" ]]; then
    echo "$BACKEND_DIR/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    echo "python3"
  else
    echo "python"
  fi
}

preflight_backend() {
  # 生产安全检查（仅告警, 不阻断）
  local env_file="$BACKEND_DIR/.env"
  if ! grep -qs '^JWT_SECRET=' "$env_file" && [[ -z "${JWT_SECRET:-}" ]]; then
    echo "[WARN] 未设置 JWT_SECRET, 后端将用内置开发默认值, 公网暴露有安全风险! 请在 backend/.env 设置强随机 JWT_SECRET"
  fi
  if ! grep -qs '^OPENCLAW_TOKEN=' "$env_file" && [[ -z "${OPENCLAW_TOKEN:-}" ]]; then
    echo "[WARN] 未设置 OPENCLAW_TOKEN, AI 对话相关接口将返回 503"
  fi
}

cmd_start_backend() {
  if pid_alive "$BACKEND_PID_FILE"; then
    echo "[INFO] backend 已在运行 PID $(cat "$BACKEND_PID_FILE")"; return 0
  fi
  if port_in_use "$BACKEND_PORT"; then
    echo "[ERR] 端口 $BACKEND_PORT 已被占用"; return 1
  fi
  local py; py="$(find_python)"
  preflight_backend
  echo "[INFO] 启动 backend(prod) python=$py host=$BIND_HOST port=$BACKEND_PORT workers=1 log=$BACKEND_LOG"
  (
    cd "$BACKEND_DIR"
    PYTHONPATH="$BACKEND_DIR" \
      nohup "$py" -m uvicorn app.main:app \
        --host "$BIND_HOST" --port "$BACKEND_PORT" \
        --workers 1 --log-level info \
        >"$BACKEND_LOG" 2>&1 &
    echo $! > "$BACKEND_PID_FILE"
  )
  sleep 2
  if pid_alive "$BACKEND_PID_FILE"; then
    echo "[OK] backend 已启动 PID $(cat "$BACKEND_PID_FILE") http://$BIND_HOST:$BACKEND_PORT"
  else
    echo "[ERR] backend 启动失败 查看 tail -n 50 $BACKEND_LOG"; return 1
  fi
}
# PLACEHOLDER2
cmd_start_frontend() {
  if pid_alive "$FRONTEND_PID_FILE"; then
    echo "[INFO] frontend 已在运行 PID $(cat "$FRONTEND_PID_FILE")"; return 0
  fi
  if port_in_use "$FRONTEND_PORT"; then
    echo "[ERR] 端口 $FRONTEND_PORT 已被占用"; return 1
  fi
  if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    echo "[ERR] node_modules 不存在 请先 cd frontend && npm install"; return 1
  fi

  # 内网环境: 不 build, 直接跑源码 dev server (vite)，/api 由 server.proxy 代理到后端
  echo "[INFO] 启动 frontend(源码 vite) host=$BIND_HOST port=$FRONTEND_PORT log=$FRONTEND_LOG"
  (
    cd "$FRONTEND_DIR"
    nohup npm run dev -- --host "$BIND_HOST" --port "$FRONTEND_PORT" \
      >>"$FRONTEND_LOG" 2>&1 &
    echo $! > "$FRONTEND_PID_FILE"
  )
  sleep 3
  if pid_alive "$FRONTEND_PID_FILE"; then
    echo "[OK] frontend 已启动 PID $(cat "$FRONTEND_PID_FILE") http://$BIND_HOST:$FRONTEND_PORT"
  else
    echo "[ERR] frontend 启动失败 查看 tail -n 80 $FRONTEND_LOG"; return 1
  fi
}

cmd_stop_one() {
  local name="$1" pid_file="$2"
  if ! pid_alive "$pid_file"; then
    echo "[INFO] $name 未运行"; rm -f "$pid_file"; return 0
  fi
  local pid; pid="$(cat "$pid_file")"
  echo "[INFO] 停止 $name PID $pid"
  kill "$pid" 2>/dev/null || true
  for _ in 1 2 3 4 5; do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
  kill -0 "$pid" 2>/dev/null && { echo "[WARN] 强制 kill -9 $pid"; kill -9 "$pid" 2>/dev/null || true; }
  rm -f "$pid_file"
  echo "[OK] $name 已停止"
}

kill_by_port() {
  if port_in_use "$1"; then
    local pids; pids="$(lsof -nP -iTCP:"$1" -sTCP:LISTEN -t 2>/dev/null || true)"
    [[ -n "$pids" ]] && { echo "[WARN] 按端口 $1 清理 $pids"; kill $pids 2>/dev/null || true; }
  fi
}
# PLACEHOLDER3
cmd_start() {
  case "${1:-all}" in
    all) cmd_start_backend; cmd_start_frontend ;;
    be)  cmd_start_backend ;;
    fe)  cmd_start_frontend ;;
    *)   echo "[ERR] 未知目标 ${1} 用 be 或 fe 或不传"; return 1 ;;
  esac
  echo
  echo "[INFO] 状态 ./scripts/prod.sh status | 日志 ./scripts/prod.sh logs [be|fe] | 停止 ./scripts/prod.sh stop"
}

cmd_stop() {
  case "${1:-all}" in
    all) cmd_stop_one "frontend" "$FRONTEND_PID_FILE"; cmd_stop_one "backend" "$BACKEND_PID_FILE"
         kill_by_port "$FRONTEND_PORT"; kill_by_port "$BACKEND_PORT" ;;
    be)  cmd_stop_one "backend" "$BACKEND_PID_FILE"; kill_by_port "$BACKEND_PORT" ;;
    fe)  cmd_stop_one "frontend" "$FRONTEND_PID_FILE"; kill_by_port "$FRONTEND_PORT" ;;
    *)   echo "[ERR] 未知目标 ${1}"; return 1 ;;
  esac
}

cmd_restart() { cmd_stop "${1:-all}"; sleep 1; cmd_start "${1:-all}"; }

cmd_status() {
  echo "=== backend(prod) ==="
  pid_alive "$BACKEND_PID_FILE" && echo "[OK] 运行中 PID $(cat "$BACKEND_PID_FILE") host=$BIND_HOST port=$BACKEND_PORT" || echo "[INFO] 未运行"
  echo "=== frontend(prod) ==="
  pid_alive "$FRONTEND_PID_FILE" && echo "[OK] 运行中 PID $(cat "$FRONTEND_PID_FILE") host=$BIND_HOST port=$FRONTEND_PORT" || echo "[INFO] 未运行"
}

cmd_logs() {
  case "${1:-be}" in
    be|backend)  tail -f "$BACKEND_LOG" ;;
    fe|frontend) tail -f "$FRONTEND_LOG" ;;
    *) echo "[ERR] 未知目标 ${1} 用 be 或 fe"; return 1 ;;
  esac
}

usage() { sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; }

case "${1:-}" in
  start)   shift; cmd_start "${1:-}" ;;
  stop)    shift; cmd_stop "${1:-}" ;;
  restart) shift; cmd_restart "${1:-}" ;;
  status)  cmd_status ;;
  logs)    shift; cmd_logs "${1:-be}" ;;
  ""|help|-h|--help) usage ;;
  *) echo "[ERR] 未知命令 $1"; usage; exit 1 ;;
esac


