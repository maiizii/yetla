# yet.la 管理平台

自托管的 yet.la 跳转管理套件，提供受 HTTP Basic 保护的管理后台与 API，用于维护子域名跳转和短链接。Nginx 会将所有 HTTP 请求 301 到 HTTPS，并将认证后的请求转发到 FastAPI 后端。

## 前置条件

- 一台已安装 Docker 与 Docker Compose 插件的 Linux 服务器（建议 Ubuntu 22.04 及以上）。
- `*.yet.la` 的 DNS 解析已指向该服务器。
- TLS 证书与私钥位于宿主机 `/root/ssl`，文件名为 `fullchain.cer` 与 `private.key`。如证书实际存在于子目录，可在宿主机创建只读符号链接：
  ```bash
  ln -s /root/ssl/your-cert-path/fullchain.cer /root/ssl/fullchain.cer
  ln -s /root/ssl/your-cert-path/private.key  /root/ssl/private.key
  ```

## 启动步骤

1. 准备环境变量：
   ```bash
   cp .env.example .env
   # 根据需要修改管理员用户名与密码
   vi .env
   ```
2. 启动服务（首次部署建议重新构建镜像）：
   ```bash
   docker compose up -d --build
   ```
3. Nginx 将监听 `80` 与 `443`，所有 HTTP 请求会被 301 跳转到 HTTPS，后端数据文件存放于 `./data` 并在容器启动时自动创建。

## 管理后台

- 入口：`https://<your-domain>/admin`
- 认证：浏览器将提示输入 `.env` 中配置的 `ADMIN_USER`/`ADMIN_PASS`。
- 后台页面直接调用 `/api/subdomains` 与 `/api/links`，失败时会显示后端返回的错误文本。

## API 调用

所有写操作均需携带 HTTP Basic 身份验证，并支持 `application/json` 与表单两种提交方式。

### JSON 示例

```bash
curl -u admin:changeme \
  -H "Content-Type: application/json" \
  -d '{"host": "foo.yet.la", "target_url": "https://example.com", "code": 302}' \
  https://yet.la/api/subdomains

curl -u admin:changeme \
  -H "Content-Type: application/json" \
  -d '{"target_url": "https://example.com/landing", "code": "promo"}' \
  https://yet.la/api/links
```

### 表单示例

```bash
# application/x-www-form-urlencoded
curl -u admin:changeme \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data "host=bar.yet.la&target_url=https://example.org&code=301" \
  https://yet.la/api/subdomains

# multipart/form-data
curl -u admin:changeme \
  -F "target_url=https://example.org/signup" \
  -F "code=winter" \
  https://yet.la/api/links
```

### 常见状态码

| 状态码 | 说明 |
| ------ | ---- |
| `200/201` | 写入成功，响应包含创建的对象。|
| `401` | 缺少或错误的 Basic Auth 凭据，包含 `WWW-Authenticate: Basic`。|
| `409` | 违反唯一约束（如短链或子域已存在）。|
| `422` | 请求参数不合法，消息中包含具体字段错误。|
| `500` | 数据库写入失败，通常由存储路径或权限问题导致。|

更多示例可使用自带的管理后台提交，所有响应均为可读文本，便于排查部署问题。
