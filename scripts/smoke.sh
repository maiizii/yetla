#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "缺少依赖: $1"
    exit 1
  fi
}

cleanup() {
  local exit_status=$?
  set +e
  if [[ -n "${subdomain_id:-}" ]]; then
    curl -sS -u "$ADMIN_USER:$ADMIN_PASS" -X DELETE \
      "$BASE_URL/api/subdomains/$subdomain_id" >/dev/null 2>&1
  fi
  if [[ -n "${short_link_id:-}" ]]; then
    curl -sS -u "$ADMIN_USER:$ADMIN_PASS" -X DELETE \
      "$BASE_URL/api/links/$short_link_id" >/dev/null 2>&1
  fi
  for file in "${tmp_files[@]}"; do
    [[ -f "$file" ]] && rm -f "$file"
  done
  return "$exit_status"
}

require_command curl
require_command python3

BASE_URL=${BASE_URL:-http://localhost:8000}
ADMIN_USER=${ADMIN_USER:-admin}
ADMIN_PASS=${ADMIN_PASS:-admin}
BASE_URL=${BASE_URL%/}

short_link_id=""
subdomain_id=""
tmp_files=()

trap cleanup EXIT

log "验收脚本启动，目标服务：$BASE_URL"

health_file=$(mktemp)
tmp_files+=("$health_file")
health_status=$(curl -sS -o "$health_file" -w "%{http_code}" "$BASE_URL/healthz" || true)
if [[ "$health_status" != "200" ]]; then
  log "健康检查失败，返回码: $health_status"
  cat "$health_file"
  exit 1
fi
log "健康检查通过"

now=$(date '+%Y%m%d%H%M%S')
short_code="smoke-${now}"
short_target="https://example.com/${short_code}"

log "创建短链接 $short_code -> $short_target"
short_payload=$(printf '{"target_url":"%s","code":"%s"}' "$short_target" "$short_code")
short_response_file=$(mktemp)
tmp_files+=("$short_response_file")
short_status=$(curl -sS -u "$ADMIN_USER:$ADMIN_PASS" \
  -H "Content-Type: application/json" \
  -d "$short_payload" \
  -o "$short_response_file" \
  -w "%{http_code}" \
  "$BASE_URL/api/links")
if [[ "$short_status" != "201" ]]; then
  log "短链创建失败，返回码: $short_status"
  cat "$short_response_file"
  exit 1
fi
short_body=$(cat "$short_response_file")
short_link_id=$(SHORT_BODY="$short_body" python3 - <<'PY'
import json
import os
body = os.environ["SHORT_BODY"]
try:
    data = json.loads(body)
except json.JSONDecodeError as exc:
    raise SystemExit(f"无法解析短链响应 JSON: {exc}")
print(data["id"])
PY
)
log "短链创建成功，ID=$short_link_id"

redirect_headers=$(mktemp)
tmp_files+=("$redirect_headers")
redirect_status=$(curl -sS -o /dev/null -D "$redirect_headers" -w "%{http_code}" \
  "$BASE_URL/r/$short_code")
if [[ "$redirect_status" != "302" ]]; then
  log "短链跳转状态码异常: $redirect_status"
  sed -n '1,20p' "$redirect_headers"
  exit 1
fi
redirect_location=$(sed -n 's/^[Ll]ocation:[[:space:]]*//p' "$redirect_headers" | tr -d '\r' | tail -n1)
if [[ "$redirect_location" != "$short_target" ]]; then
  log "短链跳转目标不匹配: $redirect_location"
  exit 1
fi
log "短链跳转校验通过"

subdomain_host="smoke-${now}.yet.la"
subdomain_target="https://example.com/subdomain/${now}"
subdomain_code=${SMOKE_SUBDOMAIN_CODE:-302}

log "创建子域跳转 $subdomain_host -> $subdomain_target (HTTP $subdomain_code)"
subdomain_payload=$(printf '{"host":"%s","target_url":"%s","code":%s}' \
  "$subdomain_host" "$subdomain_target" "$subdomain_code")
subdomain_response_file=$(mktemp)
tmp_files+=("$subdomain_response_file")
subdomain_status=$(curl -sS -u "$ADMIN_USER:$ADMIN_PASS" \
  -H "Content-Type: application/json" \
  -d "$subdomain_payload" \
  -o "$subdomain_response_file" \
  -w "%{http_code}" \
  "$BASE_URL/api/subdomains")
if [[ "$subdomain_status" != "201" ]]; then
  log "子域跳转创建失败，返回码: $subdomain_status"
  cat "$subdomain_response_file"
  exit 1
fi
subdomain_body=$(cat "$subdomain_response_file")
subdomain_id=$(SUBDOMAIN_BODY="$subdomain_body" python3 - <<'PY'
import json
import os
body = os.environ["SUBDOMAIN_BODY"]
try:
    data = json.loads(body)
except json.JSONDecodeError as exc:
    raise SystemExit(f"无法解析子域响应 JSON: {exc}")
print(data["id"])
PY
)
log "子域跳转创建成功，ID=$subdomain_id"

host_headers=$(mktemp)
tmp_files+=("$host_headers")
host_status=$(curl -sS -o /dev/null -D "$host_headers" -w "%{http_code}" \
  -H "Host: $subdomain_host" \
  "$BASE_URL/")
if [[ "$host_status" != "$subdomain_code" ]]; then
  log "Host 跳转状态码异常: $host_status"
  sed -n '1,20p' "$host_headers"
  exit 1
fi
host_location=$(sed -n 's/^[Ll]ocation:[[:space:]]*//p' "$host_headers" | tr -d '\r' | tail -n1)
if [[ "$host_location" != "$subdomain_target" ]]; then
  log "Host 跳转目标不匹配: $host_location"
  exit 1
fi
log "Host 跳转校验通过"

log "开始清理测试数据"
cleanup
trap - EXIT
log "所有验收步骤完成"
