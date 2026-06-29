#!/bin/bash
# Start dashboard backend (port 8002) + frontend dev server (port 5003)
DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$DIR/.." && pwd)"
VENV="$PROJECT_ROOT/.venv"
BACKEND_PID_FILE="$DIR/.backend.pid"
FRONTEND_PID_FILE="$DIR/.frontend.pid"

# Stop existing if running
"$DIR/stop.sh" 2>/dev/null

# Backend (CWD must be backend/ for uvicorn to find main module)
cd "$DIR/backend"

# Free port 8002 if a stale process holds it
if lsof -ti:8002 >/dev/null 2>&1; then
    echo "Port 8002 busy — killing stale process(es)"
    lsof -ti:8002 | xargs kill -9 2>/dev/null
    sleep 0.5
fi

PYTHONPATH="$DIR/backend:$PROJECT_ROOT" "$VENV/bin/uvicorn" main:app --host 0.0.0.0 --port 8002 --reload --app-dir "$DIR/backend" &
echo $! > "$BACKEND_PID_FILE"
echo "Backend started on http://localhost:8002 (PID $(cat $BACKEND_PID_FILE))"

# Frontend
if [ -d "$DIR/frontend/node_modules" ]; then
    cd "$DIR/frontend"
    npx vite --host 0.0.0.0 --port 5003 &
    echo $! > "$FRONTEND_PID_FILE"
    echo "Frontend started on http://localhost:5003 (PID $(cat $FRONTEND_PID_FILE))"
else
    echo "Frontend not installed yet. Run: cd dashboard/frontend && npm install"
fi
