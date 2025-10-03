# Changelog

本文件用于记录 yet.la 管理平台的变更。以下条目初始化了「服务端重定向」基线任务，方便后续迭代追踪。

## 2025-10-03
- 初始化变更日志，标记 server-side redirects 工作流基线。

## 2025-10-04
- 引入 SQLite 数据库初始化逻辑，新增 `SubdomainRedirect` 与 `ShortLink` 模型。
- 新增 `.env.example` 与文档说明，约定数据文件挂载到 `./data`。

## 2025-10-05
- 为 FastAPI 应用实现短链接与子域 CRUD 接口，新增 HTTP Basic 认证保护 `/api/*` 与 `/admin`。
- 增加 `/healthz`、`/r/{code}` 与 Host 通配跳转路由，未命中返回 404 文本。
- README 增补接口表与 `curl` 示例，便于人工自测。

## 2025-10-06
- 新增 `infra/nginx/conf.d/yetla.upstream.conf`，将容器内 Nginx 的入口统一代理到 `backend`。
- 提供 `docker-compose.override.yml`，默认保留 `8080:80` 并可选开启 `80:80` 暴露端口。
- README 补充部署章节，说明容器化 Nginx → backend 的统一流量入口。

## 2025-10-07
- 为 backend 服务新增 Docker Compose 健康检查，命中 `/routes` 确认数据接口可用。
- 在仓库根目录加入 `Makefile`，封装 `up/down/logs/test/shell` 常用命令。
- README 新增「一键命令」章节，介绍上述快捷指令。
