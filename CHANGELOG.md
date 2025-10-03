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
