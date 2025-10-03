#!/bin/sh
set -eu

CERT_PATTERN="/etc/nginx/ssl"/'*.yet.la_yet.la_P256'
CERT_DIR=""
for candidate in $CERT_PATTERN; do
    if [ -d "$candidate" ]; then
        CERT_DIR="$candidate"
        break
    fi
done

if [ -z "$CERT_DIR" ]; then
    echo "[entrypoint] 未找到证书目录，跳过符号链接创建" >&2
    exit 1
fi

FULLCHAIN="$CERT_DIR/fullchain.cer"
PRIVATE_KEY="$CERT_DIR/private.key"

if [ ! -f "$FULLCHAIN" ] || [ ! -f "$PRIVATE_KEY" ]; then
    echo "[entrypoint] 证书或私钥文件缺失: $CERT_DIR" >&2
    exit 1
fi

mkdir -p /etc/nginx/certs
ln -sf "$FULLCHAIN" /etc/nginx/certs/fullchain.cer
ln -sf "$PRIVATE_KEY" /etc/nginx/certs/private.key
