# 使用 Nginx 管理二级域名跳转的可行性

当所有二级域名都解析到同一台入口服务器时，可以通过 Nginx 的反向代理能力实现基于 `Host` 的动态路由，无需频繁调整 DNS 记录。Yetla 在此基础上进一步引入数据库驱动的规则管理，使得入口层不必重载即可新增/修改跳转。

## 基础前提

- DNS 层为根域和泛域名（`example.com`、`*.example.com`）指向同一台入口服务器。
- 入口服务器终止 TLS，并将请求反向代理到后端（本项目中的 FastAPI 服务）。
- 客户端请求必须携带正确的 `Host` 头，Cloudflare 等代理场景会自动保留该头部。

## Yetla 的 Nginx 架构

1. **HTTPS 终止与统一跳转**：`infra/nginx/conf.d/yetla.upstream.conf` 定义了 `80`→`443` 的 301 跳转，以及在 `443` 端口加载挂载在 `/etc/nginx/ssl/` 下的证书。
2. **反代 FastAPI**：所有请求都会转发至 `backend:8000`，并透传 `Authorization`、`Host`、`X-Forwarded-*` 等头部，后端根据数据库规则决定返回 30x 重定向还是 404。
3. **证书挂载机制**：入口脚本会在容器内 `/etc/nginx/ssl` 生成指向宿主机证书的符号链接，便于证书轮换。更新宿主机证书后执行 `docker compose restart nginx` 即可生效。
4. **冒烟验证**：`scripts/proxy-smoke.sh` 通过模拟 Cloudflare 的代理请求验证 HTTP→HTTPS 跳转、Basic Auth 保护以及子域命中。

与传统的 Nginx `map` 静态配置相比，Yetla 通过 FastAPI 接口维护子域与短链，命中时由后端返回目标地址并在数据库中记录访问次数。Nginx 本身只负责 TLS、日志与反向代理，降低了重新加载配置的复杂度。

## 适用场景与扩展

- **集中式域名管理**：适用于需要频繁增删子域跳转的场景，通过 API 或管理后台即可实时生效。
- **营销短链**：短链接命中后可以追加路径与查询参数，满足活动落地页的统计需求。
- **灰度/多环境路由**：可在 FastAPI 中扩展逻辑，根据请求头或路径做更细粒度的上游选择。

若需在 Nginx 层加入缓存、速率限制或自定义日志格式，可在 `infra/nginx/conf.d/` 目录新增配置片段，并通过 `docker-compose.override.yml` 挂载。所有变更务必配合冒烟脚本与 `docker compose logs nginx` 进行验证。
