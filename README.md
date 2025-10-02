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

## 部署建议

1. **自动生成配置**：未来可由后端根据数据库记录渲染 Nginx 模板，再通过 CI/CD 分发。
2. **热更新**：应用配置后执行 `nginx -s reload` 即可生效，无需下线服务。
3. **审计与备份**：将配置与路由数据版本化，方便回溯。

## 开发计划（Roadmap）

- [ ] 设计数据库 schema（域名记录、短链接、审计日志）
- [ ] 实现完整 CRUD API 与鉴权
- [ ] 编写前端页面或命令行交互工具
- [ ] 集成 Cloudflare API 自动同步 DNS
- [ ] 自动化部署与配置同步

欢迎在 Issue 中提出需求或建议，让 yet.la 的二级域名和短链接管理更加高效！
