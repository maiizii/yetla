#!/bin/sh
set -eu

CERT_ROOT="/etc/nginx/ssl"
FULLCHAIN="$CERT_ROOT/fullchain.cer"
PRIVATE_KEY="$CERT_ROOT/private.key"

if [ -f "$FULLCHAIN" ] && [ -f "$PRIVATE_KEY" ]; then
    echo "[entrypoint] 证书文件已就绪: $CERT_ROOT" >&2
    exit 0
fi

for candidate in "$CERT_ROOT"/*.yet.la_yet.la_P256; do
    if [ ! -d "$candidate" ]; then
        continue
    fi

    candidate_fullchain="$candidate/fullchain.cer"
    candidate_private="$candidate/private.key"

    if [ ! -f "$candidate_fullchain" ] || [ ! -f "$candidate_private" ]; then
        echo "[entrypoint] 证书目录存在但文件缺失: $candidate" >&2
        continue
    fi

    if [ -w "$CERT_ROOT" ]; then
        ln -sf "$candidate_fullchain" "$FULLCHAIN"
        ln -sf "$candidate_private" "$PRIVATE_KEY"
        echo "[entrypoint] 已将证书标准化为 $CERT_ROOT/{fullchain.cer,private.key}" >&2
        exit 0
    fi

    echo "[entrypoint] 检测到只读挂载: $CERT_ROOT" >&2
    echo "[entrypoint] 请在宿主机创建指向 $candidate 的符号链接 fullchain.cer/private.key" >&2
    exit 1
done

echo "[entrypoint] 未找到 TLS 证书，请确认 /root/ssl 已提供 fullchain.cer 与 private.key" >&2
exit 1
