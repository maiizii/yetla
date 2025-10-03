# yet.la 管理平台

自托管的 yet.la 域名跳转管理平台，提供受 HTTP Basic 保护的管理后台与 API，用于维护子域名路由与短链接。Cloudflare 负责 DNS 与 TLS
终止，Nginx 统一接受公网流量并转发到 FastAPI 后端。

## 目录

- [本仓库包含什么？](#本仓库包含什么)
- [前置条件](#前置条件)
- [快速开始](#快速开始)
- [一键命令](#一键命令)
- [验收脚本](#验收脚本)
- [HTTPS 入口与冒烟验证](#https-入口与冒烟验证)
- [安装与部署指南](#安装与部署指南)
- [证书与 Nginx 配置](#证书与-nginx-配置)
- [Cloudflare 设置](#cloudflare-设置)
- [部署完成后的使用方式](#部署完成后的使用方式)
- [API 说明与示例 curl](#api-说明与示例-curl)
- [环境变量](#环境变量)
- [数据存储](#数据存储)
- [安全基线](#安全基线)
- [测试运行](#测试运行)
- [常见故障排障](#常见故障排障)

## 本仓库包含什么？

> ✅ 当前版本提供一套可直接部署的 HTTPS 反向代理 + FastAPI 管理后端，覆盖 yet.la 全域的短链接与子域跳转管理需求。

```
.
├── apps/                  # 历史示例页面（默认部署不再挂载到 Nginx）
├── backend/               # FastAPI 服务，提供管理后台与 API
├── data/                  # SQLite 数据卷（容器启动时自动创建）
├── docs/                  # 设计文档与脚本示例
├── infra/nginx/           # Nginx 配置与入口脚本
├── docker-compose.yml     # 生产部署所用的 Compose 模板
├── docker-compose.override.yml
└── scripts/               # 自动化脚本（如备份、冒烟测试）
```

- **统一反向代理**：`infra/nginx/conf.d/yetla.upstream.conf` 监听 `80/443`，负责 HTTP→HTTPS 重定向与上游代理。
- **认证后台 + API**：`backend/app/main.py` 提供 HTMX 管理界面及 REST API，所有写操作强制 HTTP Basic 认证。
- **部署脚本**：`docker-compose*.yml` 与 `infra/nginx/docker-entrypoint.d/` 负责容器化部署与证书挂载自检。

更多背景信息请参阅 [docs/NGINX_SUBDOMAIN_ROUTING.md](docs/NGINX_SUBDOMAIN_ROUTING.md)。

## 前置条件

1. **域名解析**：在 DNS 服务商（如 Cloudflare）为 `yet.la` 与 `*.yet.la` 配置 A/AAAA 记录指向服务器公网 IP。
2. **服务器环境**：Linux（推荐 Ubuntu 22.04 LTS），具备 root/sudo 权限。
3. **运行依赖**：`git`、`docker`、`docker compose` 插件、`make`（用于 Makefile 命令）。
4. **TLS 证书**：持有覆盖 `yet.la` 与 `*.yet.la` 的证书链与私钥，后续章节提供标准化路径示例。

## 快速开始

```bash
# 1. 克隆仓库
$ git clone git@github.com:your-org/yetla.git
$ cd yetla

# 2. 准备环境变量
$ cp .env.example .env
$ vi .env   # 修改管理员用户名与密码

# 3. 启动容器（首次部署建议重新构建镜像）
$ docker compose up -d --build
```

Nginx 默认监听 `80/443`，HTTP 请求统一 301 跳转至 HTTPS 并转发至后端 `backend:8000`。

## 一键命令

项目根目录提供 `Makefile`，封装常用的 Compose 操作：

```bash
# 构建并以后台模式启动所有服务（等价于 docker compose up -d --build）
make up

# 停止并清理容器、网络与匿名卷
make down

# 持续追踪所有服务日志
make logs

# 在后端容器内运行 Pytest
make test

# 进入后端容器交互式 Shell
make shell
```

## 验收脚本

`scripts/smoke.sh` 可用于回归验证 FastAPI 接口：

- 创建短链并确认 `/r/{code}` 返回 302 与正确 `Location`；
- 创建子域跳转并使用自定义 `Host` 验证 3xx；
- 用完后自动清理。

运行前确保服务已启动并根据需要调整以下环境变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `BASE_URL` | `https://yet.la` | FastAPI 服务地址（可改为本地 IP/域名） |
| `ADMIN_USER` / `ADMIN_PASS` | `admin` / `admin` | HTTP Basic 凭据 |
| `SMOKE_SUBDOMAIN_CODE` | `302` | 子域跳转使用的状态码 |

执行示例：

```bash
bash scripts/smoke.sh
```

## HTTPS 入口与冒烟验证

容器启动后 Nginx 会：

- 在 `80` 端口返回 301 → `https://$host$request_uri`；
- 在 `443` 端口加载 `/etc/nginx/ssl/{fullchain.cer,private.key}` 并反向代理到 `backend:8000`；
- 透传 `Authorization`、`Host` 以及标准的 `X-Forwarded-*` 头。

冒烟测试示例（需替换为实际域名/IP，并信任证书）：

```bash
# 1. HTTP 自动跳转 HTTPS
curl -I http://yet.la/

# 2. 健康检查
curl -sk https://yet.la/healthz

# 3. 未授权访问返回 401（包含 WWW-Authenticate）
curl -skI https://yet.la/api/subdomains

# 4. 携带 Basic Auth 创建子域（JSON）
curl -sk -u admin:admin \
  -H "Content-Type: application/json" \
  -d '{"host":"foo.yet.la","target_url":"https://example.com","code":302}' \
  https://yet.la/api/subdomains
```

## 安装与部署指南

以下步骤在一台全新 Ubuntu 22.04 VPS 上验证通过，可按需调整：

1. **更新软件源并安装 Git（如系统自带可跳过）**
   ```bash
   sudo apt-get update
   sudo apt-get install -y git
   ```
2. **克隆仓库并进入项目目录**
   ```bash
   git clone https://github.com/your-org/yetla.git
   cd yetla
   ```
3. **安装运行依赖（Docker、Docker Compose 插件）**
   - 推荐执行仓库脚本：
     ```bash
     sudo ./scripts/setup-ubuntu.sh
     ```
   - 若无法使用脚本，可参考脚本内容手动安装。
4. **刷新 Docker 用户组（如需）**
   ```bash
   newgrp docker
   ```
5. **准备配置与数据目录**
   ```bash
   cp .env.example .env
   vi .env
   mkdir -p data
   chmod 700 data
   ```
6. **准备证书目录（详见 [证书与 Nginx 配置](#证书与-nginx-配置)）**
7. **启动服务**
   ```bash
   docker compose up -d --build
   ```
8. **验证容器状态与健康检查**
   ```bash
   docker compose ps
   curl -sk https://yet.la/healthz
   curl -sk https://yet.la/routes
   ```
9. **（可选）放行防火墙端口**
   ```bash
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   ```

完成后，可通过 `https://yet.la/admin` 登录后台或使用 API 进行管理。

## 证书与 Nginx 配置

Nginx 容器通过只读挂载 `/root/ssl -> /etc/nginx/ssl` 读取证书：

1. 在宿主机准备证书目录（示例使用 Cloudflare 签发的 ECDSA 证书）：
   ```bash
   ls /root/ssl/*.yet.la_yet.la_P256/
   # 包含 fullchain.cer 与 private.key
   ```
2. 创建指向标准文件名的只读符号链接：
   ```bash
   ln -s /root/ssl/*.yet.la_yet.la_P256/fullchain.cer /root/ssl/fullchain.cer
   ln -s /root/ssl/*.yet.la_yet.la_P256/private.key   /root/ssl/private.key
   chmod 600 /root/ssl/*.cer /root/ssl/*.key
   ```
3. `docker-compose.yml` 将 `/root/ssl` 以只读方式挂载到容器 `/etc/nginx/ssl`。入口脚本会在启动阶段检查 `fullchain.cer` 与 `private.key` 是否就绪，缺失时给出错误提示。
4. 如需轮换证书，先更新宿主机指向的目标文件，再执行 `docker compose restart nginx`。

`infra/nginx/conf.d/yetla.upstream.conf` 的核心配置片段如下：

```nginx
server {
    listen 80;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    ssl_certificate     /etc/nginx/ssl/fullchain.cer;
    ssl_certificate_key /etc/nginx/ssl/private.key;

    location / {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port 443;
    }
}
```

## Cloudflare 设置

1. **SSL/TLS 模式**：在 Cloudflare 控制台将域名的 SSL/TLS 模式设置为 **Full (strict)**，确保 Cloudflare 与源站之间使用有效证书。
2. **DNS 记录**：为 `yet.la` 与 `*.yet.la` 创建 A/AAAA 记录指向服务器公网 IP。常规运行可保持「代理状态」开启（橙色云朵）。
3. **排障模式**：若需绕过 Cloudflare 验证源站，可将记录切换为「DNS only」（灰色云朵），待问题排查完成后再恢复代理。
4. **防火墙与速率限制**：可在 Cloudflare 配置允许列表或速率限制，限制 `/admin` 与 `/api/*` 的访问来源。

## 部署完成后的使用方式

### 管理后台

- 入口：`https://<你的域名>/admin`
- 认证：浏览器弹窗要求输入 `.env` 中的 `ADMIN_USER` / `ADMIN_PASS`。
- 功能：通过 HTMX 调用 `/api/links` 与 `/api/subdomains` 完成 CRUD，错误信息会直接反馈在页面中。

### 访客访问

- `https://yet.la/`：根据子域匹配结果返回重定向或 404 文本。
- `https://yet.la/r/<code>`：短链接入口，命中后累积访问次数。

## API 说明与示例 curl

`backend/app/main.py` 提供以下接口：

| Method | Path | 说明 | 认证 | 常见返回码 |
| --- | --- | --- | --- | --- |
| GET | `/healthz` | 健康检查 | 无 | 200 |
| GET | `/routes` | 查询所有子域跳转规则 | 无 | 200 |
| GET | `/api/links` | 列出短链接 | HTTP Basic | 200 |
| POST | `/api/links` | 新增短链接（`code` 为空时自动生成） | HTTP Basic | 201 / 409 |
| DELETE | `/api/links/{id}` | 删除短链接 | HTTP Basic | 204 / 404 |
| GET | `/api/subdomains` | 列出子域跳转 | HTTP Basic | 200 |
| POST | `/api/subdomains` | 新增子域跳转（`host` 为完整域名） | HTTP Basic | 201 / 409 |
| DELETE | `/api/subdomains/{id}` | 删除子域跳转 | HTTP Basic | 204 / 404 |
| GET | `/r/{code}` | 短链接跳转并累积访问量 | 无 | 302 / 404 |

写操作同时支持 JSON 与表单提交，示例如下：

```bash
# JSON 请求体
curl -sk -u admin:changeme \
  -H "Content-Type: application/json" \
  -d '{"target_url":"https://example.com/landing","code":"promo"}' \
  https://yet.la/api/links

# application/x-www-form-urlencoded
curl -sk -u admin:changeme \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data "host=foo.yet.la&target_url=https://example.com&code=301" \
  https://yet.la/api/subdomains

# multipart/form-data
curl -sk -u admin:changeme \
  -F "target_url=https://example.org/signup" \
  -F "code=winter" \
  https://yet.la/api/links
```

常见状态码说明：

| 状态码 | 含义 |
| --- | --- |
| `200/201` | 写入成功，响应体包含创建或更新后的对象。 |
| `401` | 缺少或错误的 Basic Auth 凭据，响应附带 `WWW-Authenticate: Basic`。 |
| `409` | 唯一键冲突（如短链 code 或子域已存在），请求不会写入数据库。 |
| `404` | 目标资源不存在或未配置子域跳转。 |
| `422` | 请求参数不合法，响应包含字段级错误信息。 |

## 环境变量

参考 [`.env.example`](.env.example) 并根据需求覆盖：

| 变量名 | 说明 |
| --- | --- |
| `ADMIN_USER` | 管理后台与 API 的 Basic Auth 用户名。 |
| `ADMIN_PASS` | 管理后台与 API 的 Basic Auth 密码。 |
| `BASE_DOMAIN` | 系统管理的基础域名，例如 `yet.la`。 |
| `SHORT_CODE_LEN` | 自动生成短链接编码的默认长度（默认 `6`）。 |

## 数据存储

- 后端使用 SQLite，数据库位于容器内 `/data/data.db`。
- `docker-compose.yml` 将仓库根目录的 `./data` 挂载到容器 `/data`，FastAPI 在启动钩子中确保目录存在并创建表结构。
- 建议定期备份 `data/data.db`，可参考 [docs/backup-example.sh](docs/backup-example.sh)。

## 安全基线

- **强化 Basic Auth 凭据**：使用长度 ≥ 16 的随机密码，并定期轮换。
- **限制来源 IP**：在 Cloudflare、防火墙或前置负载均衡层对白名单 IP 开放 `/admin` 与 `/api/*`。
- **日志与备份**：将 `./data` 与容器日志纳入备份计划，可配合 cron 定期执行备份脚本。

## 测试运行

后端自带 Pytest 用例验证核心逻辑：

```bash
# 本机安装依赖后执行
pip install -r backend/requirements.txt
pytest -q

# 或在已运行的 Docker 容器中执行
docker compose exec backend pytest -q
```

## 常见故障排障

| 现象 | 可能原因 | 排查建议 |
| --- | --- | --- |
| Cloudflare 返回 `521` | 源站拒绝连接或 TLS 不匹配 | 确认容器已启动、`docker compose ps` 无异常；Cloudflare SSL/TLS 模式是否为 **Full (strict)**；临时切换 DNS-only 直接访问 `https://<源站IP>` 验证。 |
| 浏览器报 `ERR_SSL_PROTOCOL_ERROR` | 使用 HTTPS 访问 `:8080` 或未正确挂载证书 | 仅开放 `80/443`，确认宿主机 `/root/ssl/fullchain.cer` 与 `private.key` 存在且权限正确。 |
| API 返回 `401 Unauthorized` | Basic Auth 凭据缺失或错误 | 确认请求头是否包含 `Authorization: Basic ...`，并检查 `.env` 中的 `ADMIN_USER`/`ADMIN_PASS`。 |
| 创建记录时报 `409 Conflict` | 违反唯一约束（短链 code 或子域重复） | 调整请求中的 `code` 或 `host`，亦可调用 `GET /api/...` 查看现有记录。 |
| 访问子域返回 `404` | 未配置对应跳转或 Host 头未透传 | 在 Nginx/负载均衡层确认 `Host` 头保留原始值，必要时通过 `curl -H "Host: foo.yet.la" https://yet.la/` 排查。 |

遇到其他问题，可结合 `docker compose logs nginx` 与 `docker compose logs backend` 查看详细日志。
