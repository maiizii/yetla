# yet.la 管理平台

一个运行在 Linux 服务器上的轻量级管理后台，用来集中管理 `*.yet.la` 下的二级域名解析和短链接跳转规则。项目默认配合 Cloudflare 进行 DNS 解析，由 Nginx 负责 HTTP 入口。

## 目录

- [本仓库包含什么？](#本仓库包含什么)
- [前置条件](#前置条件)
- [快速开始](#快速开始)
- [一键命令](#一键命令)
- [验收脚本](#验收脚本)
- [HTTPS 入口与冒烟验证](#https-入口与冒烟验证)
- [安装与部署指南](#安装与部署指南)
- [部署完成后的使用方式](#部署完成后的使用方式)
- [API 说明与示例 curl](#api-说明与示例-curl)

## 本仓库包含什么？

> ✅ 现在已经加入一个可运行的最小化示例，演示“DNS 只做泛解析 + Nginx 按子域路由”的可行性。

```
.
├── apps/                  # 三个静态站点示例，分别映射到不同子域
├── backend/               # FastAPI 原型服务，返回子域映射数据
├── docs/                  # 设计与实现文档
├── infra/nginx/           # Nginx 配置示例（map + upstream）
└── docker-compose.yml     # 一键启动 Nginx 与示例后端
```

- **二级域名管理**：通过 `infra/nginx/conf.d/subdomains.conf` 中的 `map` 指令将子域路由到不同 upstream。
- **短链接/跳转**：可在同一配置文件中添加 `return 301/302` 规则，无需修改 DNS。
- **后端接口**：`backend/app/main.py` 提供只读接口，展示如何为 Nginx 模板提供配置数据。

更多背景信息请阅读 [docs/NGINX_SUBDOMAIN_ROUTING.md](docs/NGINX_SUBDOMAIN_ROUTING.md)。

## 前置条件

1. **域名解析**：在 DNS 服务商（如 Cloudflare）设置 `*.yet.la` 指向当前服务器。
2. **服务器环境**：Linux（推荐 Ubuntu 22.04 LTS），需要 root/sudo 权限安装依赖。
3. **运行依赖**：`git`、`docker`、`docker compose` 插件、`make`（用于 Makefile 命令）。
4. **SSL 证书**：建议通过 Cloudflare 或 ACME 自动签发。

## 快速开始

```bash
# 1. 克隆仓库
$ git clone git@github.com:your-org/yetla.git
$ cd yetla

# 2. 启动本地演示环境
$ docker compose up --build

# 3. 在本机 hosts 文件添加子域映射（示例）
127.0.0.1 yet.la
127.0.0.1 api.yet.la
127.0.0.1 console.yet.la

# 4. 浏览器访问
http://api.yet.la:8080      # 代理到 apps/api
http://console.yet.la:8080  # 命中 302 并回到 https://console.yet.la
http://yet.la:8080          # 默认站点
```

FastAPI 接口可通过 `http://localhost:8000/routes` 查看当前子域映射。

## 一键命令

项目根目录提供了 `Makefile`，将常用的 Docker Compose 操作封装为以下指令：

```bash
# 构建并启动所有服务（等价于 docker compose up -d --build）
make up

# 停止并清理容器、网络与匿名卷
make down

# 追踪所有服务的输出日志
make logs

# 在后端容器内运行 Pytest 用例
make test

# 启动后端容器的交互式 Shell
make shell
```

上述命令默认读取 `docker-compose.yml` 与 `docker-compose.override.yml`，方便在开发机快速验证路由配置与接口健康状况。

## 验收脚本

仓库提供了 `scripts/smoke.sh` 用于在本地或 CI 环境快速验收接口是否可用。脚本会：

- 调用 `POST /api/links` 创建短链并校验 `/r/{code}` 返回 302 及正确的 `Location` 头；
- 调用 `POST /api/subdomains` 创建子域跳转并通过自定义 `Host` 头确认 301/302 跳转；
- 清理新建的短链与子域记录，保持数据库整洁。

在运行脚本前请确保服务已启动（默认监听 `http://localhost:8000`），并根据需要调整以下环境变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `BASE_URL` | `http://localhost:8000` | FastAPI 服务地址 |
| `ADMIN_USER` / `ADMIN_PASS` | `admin` / `admin` | 受保护接口的 HTTP Basic 凭据 |
| `SMOKE_SUBDOMAIN_CODE` | `302` | 创建子域时使用的跳转状态码 |

执行示例：

```bash
$ bash scripts/smoke.sh
[2024-01-01 12:00:00] 验收脚本启动，目标服务：http://localhost:8000
[2024-01-01 12:00:00] 健康检查通过
[2024-01-01 12:00:01] 所有验收步骤完成
```

## HTTPS 入口与冒烟验证

Nginx 容器会读取宿主机 `/root/ssl/*.yet.la_yet.la_P256/` 目录下的证书文件，并在启动阶段通过 `docker-entrypoint.d/10-setup-cert-links.sh` 创建到 `/etc/nginx/certs/fullchain.cer` 与 `/etc/nginx/certs/private.key` 的只读符号链接。确保目录结构与权限正确后，执行 `docker compose up -d --build` 即会同时监听 `80`（仅用于 301 跳转）与 `443`（HTTPS upstream）。

部署完成后，可使用以下命令进行最小化冒烟测试：

1. **HTTP 自动跳转 HTTPS**

   ```bash
   curl -I -H "Host: yet.la" http://127.0.0.1:8080/
   ```

   期望状态码 `301`，`Location` 头指向 `https://yet.la/...`。

2. **未授权访问返回 401**

   ```bash
   curl -skI -H "Host: yet.la" https://127.0.0.1/api/subdomains
   ```

   期望状态码 `401`，并携带 `WWW-Authenticate` 响应头。

3. **携带 Basic Auth 可创建记录**

   ```bash
   curl -skI -u admin:admin -H "Host: yet.la" \
     --data "host=test.yet.la&target_url=https://example.com&code=302" \
     https://127.0.0.1/api/subdomains
   ```

   期望状态码 `200` 或 `201`，表示新增成功。

4. **命中已配置子域返回 302**

   ```bash
   curl -skI -H "Host: test.yet.la" https://127.0.0.1/
   ```

   期望状态码 `302`（或创建时指定的码），并重定向到目标地址。

为了自动化执行上述步骤，仓库新增 `scripts/proxy-smoke.sh`：

```bash
bash scripts/proxy-smoke.sh
```

脚本默认连接 `127.0.0.1:8080/443`，可通过环境变量覆盖：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `HTTP_HOST` / `HTTPS_HOST` | `127.0.0.1` | 反向代理监听地址 |
| `HTTP_PORT` / `HTTPS_PORT` | `8080` / `443` | HTTP/HTTPS 端口 |
| `BASE_DOMAIN` | `yet.la` | 发送在 `Host` 头中的主域 |
| `ADMIN_USER` / `ADMIN_PASS` | `admin` / `admin` | API 基础认证凭据 |
| `SMOKE_CODE` | `302` | 创建子域时使用的重定向状态码 |

脚本会在末尾清理临时创建的子域记录，便于重复执行。

## 安装与部署指南

以下步骤默认在一台满足「[前置条件](#前置条件)」的 Linux 服务器或本地开发机上执行。请按照顺序完成，确保环境与配置完整：

### 在全新 Ubuntu 22.04 VPS 上的完整部署步骤

> ✅ 以下命令均在一台出厂设置的 Ubuntu 22.04 LTS VPS 上验证通过，可复制粘贴执行。

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

3. **安装运行依赖（Docker、Docker Compose 插件等）**

   - 推荐运行仓库提供的脚本，一次性完成依赖配置：

     ```bash
     sudo ./scripts/setup-ubuntu.sh
     ```

   - 脚本会：
     - 安装 `ca-certificates`、`curl`、`gnupg`、`git`、`make` 等基础工具；
     - 添加 Docker 官方源并安装 `docker-ce`、`docker-compose-plugin` 等组件；
     - 启动并设为开机自启 Docker 服务；
     - 将当前用户加入 `docker` 用户组（重新登录后即可无 `sudo` 调用 `docker`）。

   - 若无法使用脚本，可参考脚本内容手动执行相同命令。

4. **重新登录或刷新用户组（必要时）**

   ```bash
   newgrp docker
   ```

   > 若仍提示「permission denied」，请退出 SSH 后重新登录，再运行后续步骤。

5. **准备环境变量与数据目录**

   ```bash
   cp .env.example .env
   nano .env          # 或者使用 vim 等编辑器修改凭据
   mkdir -p data
   chmod 700 data
   ```

   - 建议将 `ADMIN_PASS` 修改为随机高强度密码。

6. **构建并启动容器**

   ```bash
   docker compose up -d --build
   ```

7. **验证容器状态与健康检查**

   ```bash
   docker compose ps
   curl http://127.0.0.1:8000/healthz
   curl http://127.0.0.1:8000/routes
   ```

   - 如需通过 Nginx 转发访问，测试：

     ```bash
     curl -I -H "Host: yet.la" http://127.0.0.1:8080/
     ```

8. **（可选）放行防火墙端口**

   ```bash
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   ```

   根据实际部署情况调整端口与安全策略。

完成以上步骤后，应用应在 `http://服务器IP:8000`（FastAPI）与 `http://服务器IP:8080`（Nginx 演示站点）上可用。

---

1. **准备运行目录**
   - 选择合适的安装路径，例如 `/opt/yetla` 或本地任意工作目录。
   - 确保磁盘剩余空间 ≥ 1 GB，用于容器镜像、日志与 SQLite 数据文件。

2. **克隆仓库并进入项目根目录**

   ```bash
   git clone https://github.com/your-org/yetla.git
   cd yetla
   ```

3. **创建本地配置文件**
   - 根据示例复制 `.env`：

     ```bash
     cp .env.example .env
     ```

   - 编辑 `.env` 并至少调整以下变量：
     - `ADMIN_USER` / `ADMIN_PASS`：后台登录与 API 调用使用的 Basic Auth 凭据，推荐设置为长度 ≥ 16 的随机字符串。
     - `BASE_DOMAIN`：需要托管的主域名，例如 `yet.la`，后端将以此生成跳转提示。
     - `SHORT_CODE_LEN`：短链接随机编码长度，可保持默认 `6` 或根据需求调整。
   - `.env` 会被 Docker Compose 自动挂载到容器内，**不要**将包含真实凭据的 `.env` 提交到版本库。

4. **准备数据卷与可选覆盖配置**
   - 项目已包含 `data/` 目录，对应容器内的 `/data`，用于保存 SQLite 数据库和其他持久化文件。首次部署前确认目录存在并具有写权限：

     ```bash
     mkdir -p data
     chmod 700 data
     ```

  - Nginx 默认使用 `infra/nginx/conf.d/subdomains.conf`，无需再挂载 `apps/api`、`apps/console` 等静态目录。
  - 如果需要让容器化 Nginx 统一代理到 FastAPI，可保留 `docker-compose.override.yml` 以及 `infra/nginx/conf.d/yetla.upstream.conf`，其中已内置监听 `yet.la` 与所有子域的示例配置。
   - 在生产环境中，可根据实际域名与证书路径调整 `infra/nginx` 下的配置文件，然后通过挂载覆盖默认配置。

5. **启动服务**

   ```bash
   docker compose up -d --build
   ```

   - `--build` 会在镜像不存在或依赖更新时自动构建。
   - 默认会启动 `nginx` 与 `backend` 两个服务；如需临时查看日志，可执行 `docker compose logs -f`。

6. **验证部署结果**
   - 查看容器状态：`docker compose ps`
   - 进行健康检查：

     ```bash
     curl http://127.0.0.1:8000/healthz
     curl http://127.0.0.1:8000/routes
     ```

   - 若通过 Nginx 暴露在 `8080` 端口，可按需在本地 `hosts` 文件中加入 `yet.la`、`api.yet.la` 等测试域名，然后访问 `http://yet.la:8080/` 确认跳转逻辑生效。

7. **面向公网的额外配置（可选）**
   - 在 DNS 服务商（如 Cloudflare）为 `*.yet.la` 配置 A/AAAA 记录指向服务器地址，并按需开启 CDN/代理。
   - 为 Nginx 添加真实证书与 80→443 跳转，可参考 `infra/nginx` 中的模板并结合自动签发方案（如 ACME）。
   - 结合宿主机防火墙限制管理接口来源，防止未授权访问，详见[安全基线](#安全基线)。

完成以上步骤后，即可得到一个带有示例站点、可通过 API 管理短链与子域跳转的最小可运行环境。

## 部署完成后的使用方式

项目部署后，可通过前台示例站点、后台管理界面与 API 三种方式进行操作：

### 前台（访客视角）

- Nginx 根据 `infra/nginx/conf.d/subdomains.conf`（或自定义配置）中的 `map` 规则路由不同子域。
- 默认示例中：
  - 访问 `http://yet.la:8080` 命中默认站点。
  - 访问 `http://api.yet.la:8080` 会被代理到 `apps/api` 示例服务。
  - 访问 `http://console.yet.la:8080` 返回 302 并重定向到 `https://console.yet.la`，演示短链跳转能力。
- 可通过 `curl -I -H "Host: <子域>" http://127.0.0.1:8080/` 验证自定义子域路由是否生效。

### 后台（管理视角）

FastAPI 应用自带一个受 HTTP Basic 保护的管理界面，便于在浏览器中查看和维护记录：

1. 确认服务已启动后访问 `http://127.0.0.1:8080/admin`（或映射到公网的域名）。
2. 未携带凭据时会返回 401，可通过 `curl -I -H "Host: yet.la" http://127.0.0.1:8080/admin` 验证。
3. 浏览器访问时输入 `.env` 中配置的 `ADMIN_USER` / `ADMIN_PASS`（默认 `admin/admin`）后，即可看到带有「短链」「子域跳转」两个 Tab 的仪表盘，页面使用 Tailwind CSS 与 HTMX CDN 进行快速排版。

#### 短链管理

- **快速创建**：在「短链」Tab 中填写目标地址（可选填自定义编码）后提交，浏览器会调用 `POST /api/links`，成功后仅刷新列表区域并给出提示。
- **安全删除**：列表操作列提供删除按钮，点击后触发 `DELETE /api/links/{id}`，同样只刷新表格部分并返回删除成功信息。
- **实时计数**：Tab 文案与表格均会根据最新记录更新，无需手动刷新整页。
- 出现参数错误（如目标地址为空或编码冲突）时，接口返回的错误信息会直接展示在页面提示区，方便调整。

#### 二级域名跳转管理

- **可视化表单**：在「子域跳转」Tab 中填写完整 Host（如 `foo.yet.la`）、目标地址与可选状态码（默认 302），提交后即调用 `POST /api/subdomains`。
- **列表操作**：表格展示 Host、目标地址、状态码与创建时间，并提供删除按钮触发 `DELETE /api/subdomains/{id}`。
- **局部刷新**：成功创建或删除后会自动刷新计数与表格，提示信息仍保留在当前 Tab 底部的反馈区域。
- 若输入格式不符合校验要求（例如 Host 留空、状态码不在 301/302 范围），接口返回的错误原因同样会通过 HTMX 直接显示，便于即时修正。

### API 与自动化

- 所有核心能力均暴露在 FastAPI 接口下，可结合 CI/CD、定时任务或外部系统进行自动化管理。
- [API 说明与示例 curl](#api-说明与示例-curl) 列出了完整的接口列表与常用命令，可在成功部署后直接执行以验证权限与功能。
- 可配合仓库内的 `scripts/smoke.sh` 进行回归校验，确保短链与子域跳转逻辑在更新后依旧可用。

## API 说明与示例 curl

`backend/app/main.py` 提供了公开与受保护的接口组合：

> ℹ️ 出于安全与路由优先级考虑，FastAPI 默认的 `/docs` 与 `/redoc` 页面已关闭。如需查看 OpenAPI 规范可访问 `/openapi.json`，或直接使用下方示例命令调试。

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

> 🔐 受保护接口通过 HTTP Basic 认证，默认凭据来自 `ADMIN_USER` / `ADMIN_PASS` 环境变量（若未配置则为 `admin/admin`）。

以下示例演示常见调用流程（假设服务运行在本地 8000 端口）：

```bash
# 健康检查与公开路由
curl http://localhost:8000/healthz
curl http://localhost:8000/routes

# 创建短链接（code 为空自动生成）、查询并删除
curl -u admin:admin \
  -H "Content-Type: application/json" \
  -d '{"target_url":"https://yet.la/docs"}' \
  http://localhost:8000/api/links
curl -u admin:admin http://localhost:8000/api/links
curl -u admin:admin -X DELETE http://localhost:8000/api/links/1

# 创建子域跳转，随后通过 Host 头验证跳转
curl -u admin:admin \
  -H "Content-Type: application/json" \
  -d '{"host":"docs.yet.la","target_url":"https://yet.la/docs","code":302}' \
  http://localhost:8000/api/subdomains
curl -u admin:admin http://localhost:8000/api/subdomains
curl -I -H "Host: docs.yet.la" http://localhost:8000/
curl -u admin:admin -X DELETE http://localhost:8000/api/subdomains/1

# 短链接跳转与命中次数（将 <code> 替换为查询结果中的实际值）
curl -I http://localhost:8000/r/<code>
```

> 在上述示例中，`curl -I -H "Host: docs.yet.la" http://localhost:8000/` 会命中通配路由并返回数据库配置的 301/302 跳转。

## 安全基线

为避免演示环境在生产中暴露风险，建议部署前检查以下安全基线：

- **强化 HTTP Basic 凭据**：在 `.env` 或宿主环境中设置 `ADMIN_USER`/`ADMIN_PASS` 时，应使用长度 ≥ 16、混合大小写字母、数字与符号的随机密码，并周期性轮换。若使用密码管理器生成，可同时记录最后一次更新日期，避免长期复用默认凭据。
- **限制管理接口来源 IP**：建议在宿主机 Nginx（或前置负载均衡）层配置白名单，仅允许办公出口或 VPN 地址访问 `/admin`、`/api/*` 等受保护路径。例如：

  ```nginx
  # /etc/nginx/conf.d/yetla-admin.conf
  map $remote_addr $yetla_admin_allowed {
      default 0;
      # 总部出口
      203.0.113.10 1;
      # VPN 网段
      198.51.100.0/24 1;
  }

  server {
      listen 443 ssl;
      server_name yet.la;

      location ~ ^/(admin|api/) {
          if ($yetla_admin_allowed = 0) {
              return 403;
          }
          proxy_pass http://backend:8000;
          include proxy_params;
      }
  }
  ```

- **备份日志与数据卷**：`./data` 目录包含 SQLite 等持久化文件，建议与容器日志一并纳入计划性备份。可在宿主机设置 cron 任务，调用 [docs/backup-example.sh](docs/backup-example.sh) 这类脚本将数据打包并同步到远端对象存储或备份盘，同时保留至少 7 天的滚动版本。例如：

  ```cron
  0 3 * * * /opt/yetla/docs/backup-example.sh >> /var/log/backup-yetla.log 2>&1
  ```

以上措施旨在降低凭据泄漏、接口滥用与数据丢失风险，但仍需配合组织的安全审计、入侵检测与合规流程。

## 测试运行

后端项目内置了一组 Pytest 用例，用于验证短链 CRUD、子域跳转、认证与公开路由等核心行为。执行方式如下：

```bash
# 安装依赖
pip install -r backend/requirements.txt

# 在本机直接运行
pytest -q

# 若通过 Docker Compose 部署了后端容器，也可在容器内执行
docker compose exec backend pytest -q
```

## 环境变量

项目根目录提供了示例文件 [`.env.example`](.env.example)，可复制为 `.env` 并根据实际情况调整：

| 变量名 | 说明 |
| --- | --- |
| `ADMIN_USER` | 后台登录用户名（占位值，后续接入鉴权时使用）。 |
| `ADMIN_PASS` | 后台登录密码。 |
| `BASE_DOMAIN` | 系统管理的基础域名，例如 `yet.la`。 |
| `SHORT_CODE_LEN` | 生成短链接时的默认编码长度，默认 `6`。 |

当前版本会读取 `ADMIN_USER` / `ADMIN_PASS` 作为 Basic Auth 凭据，并使用 `SHORT_CODE_LEN` 控制自动生成短码长度；其余变量仍预留以便后续扩展。

## 数据存储

- 后端默认使用 SQLite，数据库文件位于容器内的 `/data/data.db`。
- `docker-compose.yml` 将仓库根目录的 `./data` 映射到容器 `/data`，首次启动 FastAPI 时会自动创建数据库文件和所需表结构（`subdomain_redirects`、`short_links`）。
- 若需备份或迁移，可直接复制 `data/data.db`。

## 部署建议

1. **自动生成配置**：未来可由后端根据数据库记录渲染 Nginx 模板，再通过 CI/CD 分发。
2. **热更新**：应用配置后执行 `nginx -s reload` 即可生效，无需下线服务。
3. **审计与备份**：将配置与路由数据版本化，方便回溯。

## 路线图

围绕「Server-side Redirects」后续迭代，基线阶段聚焦于以下检查点：

- **受影响的核心文件**：
  - `docker-compose.yml`：声明 Nginx 与 FastAPI 后端服务，后续重定向能力将依赖该编排。
  - `backend/app/main.py`：提供 `/routes` 接口，是 Nginx 模板生成与校验的当前数据源。
- **最小自检命令**：

  ```bash
  docker compose up -d
  curl http://localhost:8000/routes
  ```

后续迭代任务：

- [ ] 设计数据库 schema（域名记录、短链接、审计日志）
- [ ] 实现完整 CRUD API 与鉴权
- [ ] 编写前端页面或命令行交互工具
- [ ] 集成 Cloudflare API 自动同步 DNS
- [ ] 自动化部署与配置同步

欢迎在 Issue 中提出需求或建议，让 yet.la 的二级域名和短链接管理更加高效！
