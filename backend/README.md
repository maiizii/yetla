# Yetla Backend

`backend/` 目录包含 Yetla 平台的核心 FastAPI 服务，负责：

- 提供受 HTTP Basic 保护的管理后台（基于 HTMX）和 REST API；
- 维护短链接与子域跳转的数据库模型，并统计命中次数；
- 为公共入口提供重定向逻辑（根据 Host 或短链 code 返回 30x）。

## 本地运行

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

运行后可访问：

- `http://localhost:8000/admin`：管理后台（需 `.env` 中的 `ADMIN_USER`/`ADMIN_PASS`）。
- `http://localhost:8000/api/links`：短链 API。
- `http://localhost:8000/api/subdomains`：子域跳转 API。
- `http://localhost:8000/healthz`：健康检查。

若需自定义环境变量，可在运行前导出 `DATABASE_URL`、`SHORT_CODE_LEN`、`SESSION_SECRET` 等配置，详情参见仓库根目录的 `README.md`。

## 主要模块

- `app/main.py`：FastAPI 应用入口，定义 API、管理后台路由以及公共重定向逻辑。
- `app/views.py`：HTMX 模板视图，实现增删改查及响应片段渲染。
- `app/models.py`：SQLAlchemy 模型与引擎配置，默认使用 SQLite。
- `app/schemas.py`：Pydantic 模型，统一请求/响应数据结构。
- `app/deps.py`：依赖注入与 Basic Auth 校验。
- `tests/`：Pytest 测试覆盖主要 API 与数据流。

## 测试

```bash
pytest -q
```

也可以在 Docker 环境中通过 `docker compose exec backend pytest -q` 运行。

## 开发提示

- 管理后台使用 HTMX 触发 API 请求，请在模板中使用 `HX-Trigger` 与局部片段渲染保持页面实时刷新。
- 新增数据库字段时，优先通过 SQLAlchemy 的 `ensure_*` 辅助函数处理向后兼容，并更新 `tests/` 中的用例。
- 若将 `DATABASE_URL` 指向外部数据库，确保在部署前为应用账户授予 `CREATE TABLE`/`ALTER TABLE` 权限，以便自动迁移所需列。
