#!/bin/sh
# Wait for all uvicorn upstreams to become healthy before starting nginx.
# Used as a pre-command in supervisord so nginx doesn't bind port 8080
# until every service is ready (prevents Cloud Run's TCP probe from
# passing prematurely).

deadline=$(( $(date +%s) + 180 ))
for p in 9031 9032 9033 9034 9035 9036 9037; do
  until curl -sf "http://127.0.0.1:$p/healthz" >/dev/null; do
    if [ "$(date +%s)" -ge "$deadline" ]; then
      echo "[wait] port $p never became healthy after 180s"; exit 1
    fi
    sleep 0.5
  done
  echo "[wait] port $p healthy"
done
echo "[wait] All services healthy — starting nginx"
