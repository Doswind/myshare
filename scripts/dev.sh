#!/usr/bin/env bash
# 启动/停止 share 项目前后端 dev 服务
#
# 用法:
#   ./scripts/dev.sh start [be|fe]    启动 默认两端 可指定仅 be 或 fe
#   ./scripts/dev.sh stop [be|fe]     停止 默认两端 可指定仅一个
#   ./scripts/dev.sh restart [be|fe]  重启 默认两端 可指定仅一个
#   ./scripts/dev.sh status           查看运行状态
#   ./scripts/dev.sh logs [be|fe]     跟踪日志 默认 backend
#   ./scripts/dev.sh tail [be|fe]     显示最近 100 行日志
#
# 后端默认端口 8000 前端默认 5173
# PID 文件写入 .run/ 日志写入 logs/

set -eo pipefail
# macOS 自带 bash 3.2 在 set -u 下对 local var; var=$(cmd) 有 bug 故不启用 -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"

RUN_DIR="$ROOT/.run"
LOG_DIR="$ROOT/logs"
mkdir -p "$RUN_DIR" "$LOG_DIR"

BACKEND_PID_FILE="$RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

pid_alive() {
  local pid_file="$1"
  [[ -f "$pid_file" ]] || return 1
  local pid; pid="$(cat "$pid_file" 2>/dev/null || true)"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

port_in_use() {
  local port="$1"
  lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | grep -q LISTEN
}

find_python() {
  if [[ -x "$BACKEND_DIR/.venv/bin/python" ]]; then
    echo "$BACKEND_DIR/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    echo "python3"
  else
    echo "python"
  fi
}

cmd_start_backend() {
  if pid_alive "$BACKEND_PID_FILE"; then
    echo "[INFO] backend 已在运行 PID $(cat "$BACKEND_PID_FILE")"
    return 0
  fi
  if port_in_use "$BACKEND_PORT"; then
    echo "[ERR] 端口 $BACKEND_PORT 已被占用 请先 stop 或手动处理"
    return 1
  fi
  if [[ ! -d "$BACKEND_DIR" ]]; then
    echo "[ERR] 后端目录不存在 $BACKEND_DIR"
    return 1
  fi

  local py
  py="$(find_python)"
  if [[ -z "$py" ]]; then echo "[ERR] 找不到可用的 Python 解释器"; return 1; fi
  echo "[INFO] 启动 backend python=$py port=$BACKEND_PORT log=$BACKEND_LOG"

  (
    cd "$BACKEND_DIR"
    PYTHONPATH="$BACKEND_DIR" \
      nohup "$py" -m uvicorn app.main:app \
        --host 127.0.0.1 --port "$BACKEND_PORT" \
        --reload --log-level warning \
        >"$BACKEND_LOG" 2>&1 &
    echo $! > "$BACKEND_PID_FILE"
  )

  sleep 2
  if pid_alive "$BACKEND_PID_FILE"; then
    echo "[OK] backend 已启动 PID $(cat "$BACKEND_PID_FILE") http://127.0.0.1:$BACKEND_PORT"
  else
    echo "[ERR] backend 启动失败 查看日志 tail -n 50 $BACKEND_LOG"
    return 1
  fi
}

cmd_start_frontend() {
  if pid_alive "$FRONTEND_PID_FILE"; then
    echo "[INFO] frontend 已在运行 PID $(cat "$FRONTEND_PID_FILE")"
    return 0
  fi
  if port_in_use "$FRONTEND_PORT"; then
    echo "[ERR] 端口 $FRONTEND_PORT 已被占用"
    return 1
  fi
  if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    echo "[ERR] node_modules 不存在 请先 cd frontend && npm install"
    return 1
  fi

  echo "[INFO] 启动 frontend vite port=$FRONTEND_PORT log=$FRONTEND_LOG"
  (
    cd "$FRONTEND_DIR"
    nohup npm run dev -- --port "$FRONTEND_PORT" \
      >"$FRONTEND_LOG" 2>&1 &
    echo $! > "$FRONTEND_PID_FILE"
  )

  sleep 3
  if pid_alive "$FRONTEND_PID_FILE"; then
    echo "[OK] frontend 已启动 PID $(cat "$FRONTEND_PID_FILE") http://127.0.0.1:$FRONTEND_PORT"
  else
    echo "[ERR] frontend 启动失败 查看日志 tail -n 50 $FRONTEND_LOG"
    return 1
  fi
}

cmd_stop_one() {
  local name="$1" pid_file="$2"
  if ! pid_alive "$pid_file"; then
    echo "[INFO] $name 未运行"
    rm -f "$pid_file"
    return 0
  fi
  local pid; pid="$(cat "$pid_file")"
  echo "[INFO] 停止 $name PID $pid"
  kill "$pid" 2>/dev/null || true
  for _ in 1 2 3 4 5; do
    kill -0 "$pid" 2>/dev/null || break
    sleep 1
  done
  if kill -0 "$pid" 2>/dev/null; then
    echo "[WARN] $name 未在 5 秒内退出 强制 kill -9"
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$pid_file"
  echo "[OK] $name 已停止"
}

kill_by_port() {
  local port="$1"
  if port_in_use "$port"; then
    echo "[WARN] 端口 $port 仍被占用 按端口清理"
    local pids; pids="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null || true)"
    [[ -n "$pids" ]] && kill $pids 2>/dev/null || true
  fi
}

cmd_start() {
  local target="${1:-all}"
  case "$target" in
    all)  cmd_start_backend; cmd_start_frontend ;;
    be)   cmd_start_backend ;;
    fe)   cmd_start_frontend ;;
    *)    echo "[ERR] 未知目标 $target 用 be 或 fe 或不传"; return 1 ;;
  esac
  echo
  echo "[INFO] 日志查看 ./scripts/dev.sh logs [be|fe]"
  echo "[INFO] 停止服务 ./scripts/dev.sh stop [be|fe]"
}

cmd_stop() {
  local target="${1:-all}"
  case "$target" in
    all)
      cmd_stop_one "frontend" "$FRONTEND_PID_FILE"
      cmd_stop_one "backend"  "$BACKEND_PID_FILE"
      kill_by_port "$FRONTEND_PORT"
      kill_by_port "$BACKEND_PORT"
      ;;
    be)
      cmd_stop_one "backend" "$BACKEND_PID_FILE"
      kill_by_port "$BACKEND_PORT"
      ;;
    fe)
      cmd_stop_one "frontend" "$FRONTEND_PID_FILE"
      kill_by_port "$FRONTEND_PORT"
      ;;
    *)
      echo "[ERR] 未知目标 $target 用 be 或 fe 或不传"
      return 1
      ;;
  esac
}

cmd_restart() {
  local target="${1:-all}"
  cmd_stop "$target"
  sleep 1
  cmd_start "$target"
}

cmd_status() {
  echo "=== backend ==="
  if pid_alive "$BACKEND_PID_FILE"; then
    echo "[OK] 运行中 PID $(cat "$BACKEND_PID_FILE") port=$BACKEND_PORT"
  else
    echo "[INFO] 未运行"
  fi
  echo "=== frontend ==="
  if pid_alive "$FRONTEND_PID_FILE"; then
    echo "[OK] 运行中 PID $(cat "$FRONTEND_PID_FILE") port=$FRONTEND_PORT"
  else
    echo "[INFO] 未运行"
  fi
  echo "=== 端口占用 ==="
  for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
    if port_in_use "$port"; then
      echo "[WARN] $port 已占用"
    else
      echo "[INFO] $port 空闲"
    fi
  done
}

cmd_logs() {
  local target="${1:-be}"
  case "$target" in
    be|backend)   tail -f "$BACKEND_LOG" ;;
    fe|frontend)  tail -f "$FRONTEND_LOG" ;;
    *) echo "[ERR] 未知目标 $target 用 be 或 fe"; return 1 ;;
  esac
}

cmd_tail() {
  local target="${1:-be}"
  case "$target" in
    be|backend)   tail -n 100 "$BACKEND_LOG" ;;
    fe|frontend)  tail -n 100 "$FRONTEND_LOG" ;;
    *) echo "[ERR] 未知目标 $target"; return 1 ;;
  esac
}

usage() {
  sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
}

case "${1:-}" in
  start)   shift; cmd_start "${1:-}" ;;
  stop)    shift; cmd_stop "${1:-}" ;;
  restart) shift; cmd_restart "${1:-}" ;;
  status)  cmd_status ;;
  logs)    shift; cmd_logs "${1:-be}" ;;
  tail)    shift; cmd_tail "${1:-be}" ;;
  ""|help|-h|--help) usage ;;
  *) echo "[ERR] 未知命令 $1"; usage; exit 1 ;;
esac
