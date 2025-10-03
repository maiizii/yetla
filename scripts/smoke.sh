#!/usr/bin/env bash
set -euo pipefail

for bin in docker curl python3; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "Missing dependency: $bin" >&2
    exit 1
  fi
done

COMPOSE_FILES=("-f" "docker-compose.yml" "-f" "docker-compose.override.yml")

docker compose "${COMPOSE_FILES[@]}" up -d --build

wait_for() {
  local url=$1
  for _ in {1..30}; do
    if curl -sSf "$url" >/dev/null; then
      return 0
    fi
    sleep 1
  done
  return 1
}

wait_for "http://127.0.0.1:8000/healthz"

curl -sSf "http://127.0.0.1:8000/routes" >/dev/null

ADMIN_USER=${ADMIN_USER:-admin}
PRIMARY_PASS=${ADMIN_PASS:-change_me_now}
FALLBACK_PASS=${SMOKE_ADMIN_FALLBACK:-admin}

create_payload='{"code":"hi","target_url":"https://google.com"}'

attempt_create() {
  local password=$1
  curl -sS -o /dev/null -w "%{http_code}" \
    -u "$ADMIN_USER:$password" \
    -H "Content-Type: application/json" \
    -d "$create_payload" \
    "http://127.0.0.1:8000/api/links"
}

create_status=$(attempt_create "$PRIMARY_PASS")

if [[ "$create_status" == "401" && "$PRIMARY_PASS" != "$FALLBACK_PASS" ]]; then
  PRIMARY_PASS="$FALLBACK_PASS"
  create_status=$(attempt_create "$PRIMARY_PASS")
fi

if [[ "$create_status" == "409" ]]; then
  existing_links=$(curl -sS -u "$ADMIN_USER:$PRIMARY_PASS" "http://127.0.0.1:8000/api/links")
  existing_id=$(LINKS="$existing_links" python3 - <<'PY'
import json
import os

payload = os.environ.get("LINKS", "[]")
try:
    data = json.loads(payload)
except json.JSONDecodeError:
    data = []

for item in data:
    if isinstance(item, dict) and item.get("code") == "hi":
        print(item.get("id", ""))
        break
PY
  )

  if [[ -n "$existing_id" ]]; then
    curl -sS -o /dev/null -u "$ADMIN_USER:$PRIMARY_PASS" \
      -X DELETE "http://127.0.0.1:8000/api/links/$existing_id"
  fi

  create_status=$(attempt_create "$PRIMARY_PASS")
fi

if [[ "$create_status" != "201" ]]; then
  echo "Failed to create short link, status: $create_status" >&2
  exit 1
fi

redirect_headers=$(mktemp)
trap 'rm -f "$redirect_headers"' EXIT

curl -sSI "http://127.0.0.1:8080/r/hi" >"$redirect_headers"
redirect_status=$(head -n 1 "$redirect_headers" | awk '{print $2}')
if [[ ! "$redirect_status" =~ ^30[0-9]$ ]]; then
  echo "Unexpected redirect status: $redirect_status" >&2
  exit 1
fi

location_header=$(grep -i '^Location:' "$redirect_headers" | tail -n1 | tr -d '\r' | cut -d' ' -f2-)
if [[ "$location_header" != "https://google.com" ]]; then
  echo "Unexpected redirect location: $location_header" >&2
  exit 1
fi

trap - EXIT
rm -f "$redirect_headers"

echo "SMOKE OK"
