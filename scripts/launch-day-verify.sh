#!/usr/bin/env bash
# Pre-launch verification — safe while early-access gate is still closed.
# Read-only against public URLs + local preflight when env files exist.
#
# Usage:
#   ./scripts/launch-day-verify.sh
#   CONFIRM_LAUNCH_DAY_VERIFY=1 ./scripts/launch-day-verify.sh  # required on VM

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

warn() { printf '\033[33mWARN  %s\033[0m\n' "$*"; }
ok() { printf '\033[32mOK    %s\033[0m\n' "$*"; }
fail() { printf '\033[31mFAIL  %s\033[0m\n' "$*"; errors=$((errors + 1)); }

errors=0

echo "=== Flint Apply launch-day verify (gate may stay closed) ==="

if [[ -f backend/.env.staging ]] && [[ -f .env.staging ]]; then
  if PRODUCTION_ENV_CHECK=1 ./scripts/production-preflight.sh; then
    ok "production-preflight"
  else
    fail "production-preflight"
  fi
else
  warn "No .env.staging on this machine — skipping PRODUCTION_ENV_CHECK"
fi

API="${LAUNCH_VERIFY_API_URL:-https://api.flintapply.com}"
SITE="${LAUNCH_VERIFY_SITE_URL:-https://flintapply.com}"

health_json="$(curl -sf "${API}/health" 2>/dev/null || true)"
if [[ -n "$health_json" ]]; then
  ok "${API}/health reachable"
  if echo "$health_json" | grep -q '"redis"'; then
    if echo "$health_json" | grep -q '"redis":"ok"'; then
      ok "health redis=ok"
    else
      warn "health redis not ok: $health_json"
    fi
  fi
else
  fail "${API}/health unreachable"
fi

free_tier="$(curl -sf "${API}/api/billing/free-tier" 2>/dev/null || true)"
if [[ -n "$free_tier" ]]; then
  ok "free-tier endpoint"
  echo "    $free_tier"
else
  warn "free-tier endpoint failed (auth? deploy?)"
fi

dash_headers="$(curl -sI "${SITE}/dashboard" 2>/dev/null | tr -d '\r' || true)"
if echo "$dash_headers" | grep -qi 'location:.*launch-preview'; then
  ok "marketing gate active (/dashboard → launch-preview) — expected before open"
elif echo "$dash_headers" | grep -qi 'location:.*auth'; then
  ok "marketing gate open (/dashboard → auth, not launch-preview)"
else
  warn "/dashboard gate state unclear; inspect in incognito"
fi

if [[ -f backend/.env.staging ]]; then
  if grep -qE '^(TURNSTILE_SITE_KEY|TURNSTILE_SECRET_KEY)=.*(1x00000000000000000000AA|2x00000000000000000000AB|1x0000000000000000000000000000000AA)' backend/.env.staging 2>/dev/null; then
    if [[ "${CONFIRM_LAUNCH_DAY_VERIFY:-0}" = "1" ]]; then
      fail "Turnstile dummy keys in backend/.env.staging — set live Cloudflare keys before public launch"
    else
      warn "Turnstile dummy keys in backend/.env.staging (FAIL when CONFIRM_LAUNCH_DAY_VERIFY=1 on VM)"
    fi
  else
    ok "Turnstile keys are not Cloudflare dummies (local env file)"
  fi
fi

contract_credits="${LAUNCH_EXPECT_STARTING_CREDITS:-6}"
if [[ -n "$free_tier" ]] && command -v python3 >/dev/null; then
  live_credits="$(python3 -c "import json,sys; print(json.loads(sys.argv[1]).get('starting_credits',''))" "$free_tier" 2>/dev/null || true)"
  if [[ -n "$live_credits" && "$live_credits" != "$contract_credits" ]]; then
    warn "live starting_credits=${live_credits} (contract/tests expect ${contract_credits}) — align admin tier_limits or marketing copy"
  elif [[ "$live_credits" == "$contract_credits" ]]; then
    ok "starting_credits matches contract (${contract_credits})"
  fi
fi

echo
echo "Operator reminders (not automated):"
echo "  - Lightsail snapshot before launch-day-open-gate.sh"
echo "  - RAM >= 8GB, swap enabled, firewall 80/443/22 only"
echo "  - Real Turnstile keys when APP_ENV=staging on VM (dummy keys bypass bots)"
echo "  - curl ${API}/api/billing/free-tier vs admin tier_limits_config (starting_credits)"
echo "  - Stop mailpit on VM if running: docker ps | grep mailpit"

if [[ "${CONFIRM_LAUNCH_DAY_VERIFY:-0}" = "1" ]]; then
  ok "CONFIRM_LAUNCH_DAY_VERIFY=1 acknowledged"
fi

echo
if [[ "$errors" -gt 0 ]]; then
  echo "Verify finished with $errors failure(s)"
  exit 1
fi
echo "Verify finished — run launch-day-open-gate.sh only on launch morning."
exit 0
