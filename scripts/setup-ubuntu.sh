#!/usr/bin/env bash
# Bootstrap script for a fresh Ubuntu 22.04 VPS to run yet.la stack.
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "[错误] 请以 root 或使用 sudo 运行本脚本" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y ca-certificates curl gnupg lsb-release git make

install -m 0755 -d /etc/apt/keyrings
if [[ ! -f /etc/apt/keyrings/docker.gpg ]]; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
fi
chmod a+r /etc/apt/keyrings/docker.gpg

# 添加 Docker 官方软件源
. /etc/os-release
cat <<REPO >/etc/apt/sources.list.d/docker.list
deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  ${VERSION_CODENAME} stable
REPO

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable --now docker

if systemctl is-active --quiet docker; then
  echo "[信息] Docker 服务已启动"
else
  echo "[警告] Docker 服务未正常启动，请检查 systemctl status docker" >&2
fi

# 将当前 sudo 用户加入 docker 组，方便无 sudo 运行 docker 命令
if [[ -n "${SUDO_USER:-}" ]]; then
  usermod -aG docker "${SUDO_USER}"
  target_user="${SUDO_USER}"
elif [[ -n "${TARGET_USER:-}" ]]; then
  usermod -aG docker "${TARGET_USER}"
  target_user="${TARGET_USER}"
else
  target_user=""
fi

cat <<INFO

依赖安装完成：
  - $(docker --version)
  - $(docker compose version)

若刚将用户添加到 docker 组，请重新登录终端后再执行 docker 命令。
INFO

if [[ -n "${target_user}" ]]; then
  echo "[提示] 用户 ${target_user} 已加入 docker 组。若为当前会话，请执行 \"newgrp docker\" 或重新登录。"
fi
