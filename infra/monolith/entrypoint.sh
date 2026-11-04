#!/bin/bash
set -e

# Start supervisord in the background (all uvicorns start, nginx does NOT —
# autostart=false).  This keeps port 8080 closed until every upstream is ready,
# so Cloud Run's TCP startup probe won't pass prematurely.
/usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf &
SUPERVISOR_PID=$!

PORTS="9031 9032 9033 9034 9035 9036 9037"
MAX_WAIT=120   # seconds
ELAPSED=0

echo "[entrypoint] Waiting for all uvicorn processes to become healthy..."

for port in $PORTS; do
    while ! curl -sf "http://127.0.0.1:${port}/healthz" > /dev/null 2>&1; do
        sleep 0.5
        ELAPSED=$((ELAPSED + 1))
        if [ "$ELAPSED" -ge "$((MAX_WAIT * 2))" ]; then
            echo "[entrypoint] ERROR: port ${port} not healthy after ${MAX_WAIT}s — aborting"
            kill "$SUPERVISOR_PID" 2>/dev/null || true
            exit 1
        fi
    done
    echo "[entrypoint] Port ${port} is healthy"
done

echo "[entrypoint] All services healthy — starting nginx"
supervisorctl start nginx

# Wait on supervisord so the container stays alive
wait "$SUPERVISOR_PID"
