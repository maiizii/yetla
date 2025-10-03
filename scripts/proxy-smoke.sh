#!/usr/bin/env bash
# 最小化冒烟脚本：验证 Nginx HTTPS 反代是否按预期工作。
set -euo pipefail

HTTP_HOST=${HTTP_HOST:-127.0.0.1}
HTTPS_HOST=${HTTPS_HOST:-127.0.0.1}
HTTP_PORT=${HTTP_PORT:-8080}
HTTPS_PORT=${HTTPS_PORT:-443}
BASE_DOMAIN=${BASE_DOMAIN:-yet.la}
ADMIN_USER=${ADMIN_USER:-admin}
ADMIN_PASS=${ADMIN_PASS:-admin}
SMOKE_CODE=${SMOKE_CODE:-302}
TMP_DIR=$(mktemp -d)
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

log() {
  printf '[proxy-smoke] %s\n' "$*"
}

check_http_redirect() {
  log "检查 HTTP→HTTPS 跳转"
  local output
  output=$(curl -sS -o /dev/null -D - -H "Host: $BASE_DOMAIN" "http://$HTTP_HOST:$HTTP_PORT/" || true)
  echo "$output" | grep -qi '^HTTP/.* 301' || { echo "$output"; log "HTTP 未返回 301"; return 1; }
  echo "$output" | grep -qi "^Location: https://" || { echo "$output"; log "Location 未指向 HTTPS"; return 1; }
}

check_unauthorized() {
  log "检查未授权访问返回 401"
  local output
  output=$(curl -skS -o /dev/null -D - -H "Host: $BASE_DOMAIN" "https://$HTTPS_HOST:$HTTPS_PORT/api/subdomains" || true)
  echo "$output" | grep -qi '^HTTP/.* 401' || { echo "$output"; log "未返回 401"; return 1; }
  echo "$output" | grep -qi '^WWW-Authenticate:' || { echo "$output"; log "缺少 WWW-Authenticate 头"; return 1; }
}

create_subdomain() {
  local ts payload response status id_file id
  ts=$(date +%s)
  TEST_HOST="proxy-smoke-${ts}.${BASE_DOMAIN}"
  payload="host=$TEST_HOST&target_url=https://example.com/proxy-smoke&code=$SMOKE_CODE"
  response="$TMP_DIR/create.json"
  log "使用 Basic Auth 创建子域跳转"
  status=$(curl -skS -u "$ADMIN_USER:$ADMIN_PASS" -o "$response" -w '%{http_code}' -H "Host: $BASE_DOMAIN" -H "Content-Type: application/x-www-form-urlencoded" -X POST --data "$payload" "https://$HTTPS_HOST:$HTTPS_PORT/api/subdomains")
  if [[ "$status" != "200" && "$status" != "201" ]]; then
    log "创建返回码异常: $status"
    cat "$response"
    return 1
  fi
  id_file="$TMP_DIR/id.txt"
  python3 - "$response" "$id_file" <<'PY'
import json
import sys
with open(sys.argv[1], 'r', encoding='utf-8') as fp:
    data = json.load(fp)
with open(sys.argv[2], 'w', encoding='utf-8') as fh:
    fh.write(str(data['id']))
PY
  SUBDOMAIN_ID=$(cat "$id_file")
  log "子域创建成功，ID=$SUBDOMAIN_ID"
}

check_host_redirect() {
  log "验证子域命中返回 $SMOKE_CODE"
  local output expected
  expected="$SMOKE_CODE"
  output=$(curl -skS -o /dev/null -D - -H "Host: $TEST_HOST" "https://$HTTPS_HOST:$HTTPS_PORT/" || true)
  echo "$output" | grep -qi "^HTTP/.* $expected" || { echo "$output"; log "返回码不是 $expected"; return 1; }
  echo "$output" | grep -qi '^Location: https://example.com/proxy-smoke' || { echo "$output"; log "Location 不匹配"; return 1; }
}

cleanup_subdomain() {
  if [[ -n "${SUBDOMAIN_ID:-}" ]]; then
    curl -skS -u "$ADMIN_USER:$ADMIN_PASS" -H "Host: $BASE_DOMAIN" -X DELETE "https://$HTTPS_HOST:$HTTPS_PORT/api/subdomains/$SUBDOMAIN_ID" >/dev/null || true
  fi
}

main() {
  check_http_redirect
  check_unauthorized
  create_subdomain
  trap 'cleanup_subdomain; cleanup' EXIT
  check_host_redirect
  cleanup_subdomain
  trap - EXIT
  cleanup
  log "全部检查通过"
}

main "$@"
