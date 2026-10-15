#!/usr/bin/env bash
# Open public signup — run ONLY on launch morning after snapshot + verify.
# Sets LAUNCH_AT / NEXT_PUBLIC_LAUNCH_AT to a past instant and rebuilds frontend+backend.
#
# Usage (on production VM, in repo root):
#   CONFIRM_LAUNCH_DAY_OPEN=1 ./scripts/launch-day-open-gate.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "${CONFIRM_LAUNCH_DAY_OPEN:-0}" != "1" ]]; then
  echo "Refusing to open launch gate without CONFIRM_LAUNCH_DAY_OPEN=1"
  echo "Run launch-day-verify.sh first. Take a Lightsail snapshot before this script."
  exit 1
fi

PAST_ISO="${LAUNCH_OPEN_AT:-2020-01-01T00:00:00Z}"
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.staging.yml -f docker-compose.prod-vm.yml)

set_launch_var() {
  local file="$1"
  local key="$2"
  local value="$3"
  if [[ ! -f "$file" ]]; then
    echo "Missing $file"
    exit 1
  fi
  if grep -q "^${key}=" "$file" 2>/dev/null; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$file"
  else
    printf '\n%s=%s\n' "$key" "$value" >>"$file"
  fi
}

echo "=== Opening launch gate (LAUNCH_AT=${PAST_ISO}) ==="

set_launch_var ".env.staging" "NEXT_PUBLIC_LAUNCH_AT" "$PAST_ISO"
set_launch_var ".env.staging" "LAUNCH_AT" "$PAST_ISO"
set_launch_var "backend/.env.staging" "LAUNCH_AT" "$PAST_ISO"

export LAUNCH_AT="$PAST_ISO"
export NEXT_PUBLIC_LAUNCH_AT="$PAST_ISO"

PRODUCTION_ENV_CHECK=1 ./scripts/production-preflight.sh

echo "Resolved launch env:"
"${COMPOSE[@]}" config 2>/dev/null | grep -i launch_at || true

echo "Rebuilding frontend (NEXT_PUBLIC_LAUNCH_AT is build-time) and backend..."
"${COMPOSE[@]}" up -d --build --no-deps frontend backend

echo "Waiting for backend health..."
for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "Local checks (via loopback; Caddy serves public HTTPS):"
curl -sf "http://127.0.0.1:8000/health" | head -c 200 || echo "WARN: backend health failed on loopback"
code="$(curl -sI "http://127.0.0.1:3000/auth" 2>/dev/null | head -1 || true)"
echo "frontend /auth: ${code:-unreachable}"

echo
echo "Next: incognito https://flintapply.com/auth (no /launch-preview redirect), then:"
echo "  CONFIRM_PRODUCTION_SMOKE=1 ./scripts/production-smoke.sh"
