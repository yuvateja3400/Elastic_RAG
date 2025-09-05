#!/usr/bin/env bash
set -euo pipefail

# ---- Config ----
API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-8000}"
UI_PORT="${UI_PORT:-8501}"
OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1}"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-phi3:mini}"

# Load .env if present
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

mkdir -p logs

echo "==> Checking Ollama on http://${OLLAMA_HOST}:${OLLAMA_PORT}"
if ! curl -sf "http://${OLLAMA_HOST}:${OLLAMA_PORT}/api/tags" >/dev/null 2>&1; then
  echo "==> Starting ollama serve (local, macOS) ..."
  nohup ollama serve > logs/ollama.log 2>&1 &
  OLLAMA_PID=$!
  # Wait until port is ready
  for i in {1..60}; do
    if curl -sf "http://${OLLAMA_HOST}:${OLLAMA_PORT}/api/tags" >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
fi

echo "==> Ensuring model '${OLLAMA_MODEL}' is present ..."
# Pull is idempotent; if it exists, this is quick.
ollama pull "${OLLAMA_MODEL}" || true

echo "==> Starting FastAPI ..."
nohup uvicorn app.api.server:app --host "${API_HOST}" --port "${API_PORT}" --reload > logs/api.log 2>&1 &
API_PID=$!

# Wait for /healthz
for i in {1..60}; do
  if curl -sf "http://127.0.0.1:${API_PORT}/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "==> Starting Streamlit UI ..."
# Point the UI to our API (can also change in the UI sidebar)
export RAG_API_BASE="http://127.0.0.1:${API_PORT}"
nohup streamlit run app/ui/streamlit_app.py --server.port "${UI_PORT}" --server.headless true > logs/ui.log 2>&1 &
UI_PID=$!

echo ""
echo "✅ All set!"
echo "   API     → http://127.0.0.1:${API_PORT}"
echo "   UI      → http://127.0.0.1:${UI_PORT}"
echo "   Ollama  → http://${OLLAMA_HOST}:${OLLAMA_PORT} (model: ${OLLAMA_MODEL})"
echo "   Logs    → ./logs/{ollama.log,api.log,ui.log}"
echo ""

cleanup() {
  echo ""
  echo "⏹  Shutting down..."
  # Only kill Ollama if we started it
  if [ -n "${OLLAMA_PID:-}" ] && ps -p "${OLLAMA_PID}" > /dev/null 2>&1; then
    kill "${OLLAMA_PID}" || true
  fi
  kill "${API_PID}" "${UI_PID}" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Keep the script in the foreground while children run
wait
