# Yetla Backend 原型

本目录包含一个最小可运行的 FastAPI 应用，演示如何对外提供子域路由配置，供 Nginx 模板渲染或后续自动化脚本使用。

## 本地运行

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

访问 `http://localhost:8000/routes` 查看目前静态配置的子域映射。

## 后续拓展建议

- 将 `ROUTES` 替换为数据库或配置文件存储，并增加 CRUD 接口。
- 返回数据可用于渲染 Nginx 模板，实现配置自动生成。
- 集成身份认证、审计日志等企业级能力。
