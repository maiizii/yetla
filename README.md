# yet.la 管理平台

一个运行在 Linux 服务器上的轻量级管理后台，用来集中管理 `*.yet.la` 下的二级域名解析和短链接跳转规则。项目默认配合 Cloudflare 进行 DNS 解析，由 Nginx 负责 HTTP 入口。

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
2. **服务器环境**：Linux (推荐 Ubuntu 20.04 及以上)，已安装 Docker 与 Docker Compose。
3. **SSL 证书**：建议通过 Cloudflare 或 ACME 自动签发。

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

## 部署

默认的 `docker-compose.yml` 仍保留示例站点路由，方便验证静态 upstream 的写法。若要让容器化 Nginx 统一代理到 FastAPI backend，只需保留同目录下的 `docker-compose.override.yml`：

- `infra/nginx/conf.d/yetla.upstream.conf`：监听 `yet.la` 与所有子域，将流量透传到 `backend:8000`，并传递 `Host`、`X-Forwarded-*` 等头部。
- `docker-compose.override.yml`：在开发机同时暴露 `8080:80` 与可选的 `80:80`，并将上述配置挂载为 Nginx 的默认入口。

运行 `docker compose up -d --build` 后，访问 `http://127.0.0.1:8080/`，即可通过后端提供的 `SubdomainRedirect` 数据命中 301/302 跳转。

## API 说明与示例 curl

`backend/app/main.py` 提供了公开与受保护的接口组合：

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

## 后台使用

FastAPI 应用自带一个受 HTTP Basic 保护的管理界面，便于在浏览器中查看数据库记录：

1. 启动 `docker compose up --build` 后访问 `http://127.0.0.1:8080/admin`。
2. 未携带凭据时会返回 401，可通过以下命令验证：

   ```bash
   curl -I -H "Host: yet.la" http://127.0.0.1:8080/admin
   ```

3. 浏览器访问时输入 `ADMIN_USER` / `ADMIN_PASS`（默认 `admin/admin`）后即可看到带有「短链」「子域跳转」两个 Tab 的仪表盘，页面使用 Tailwind CSS 与 HTMX CDN 进行快速排版。（截图占位，后续补充）

> 页面当前以只读方式展示数据，仍建议通过 API 完成增删改操作。

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
