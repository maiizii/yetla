# Nginx 子域路由配置

该目录存放使用 Nginx 解析二级域名的示例配置。核心思想是：

1. 通过 DNS 将 `*.yet.la` 指向同一台服务器（可以是 A 记录或 CNAME）。
2. Nginx 根据请求头中的 `Host` 字段选择不同的 upstream，达到“子域内部分流”的目的。
3. 当需要新增子域时，只需更新 map 表并重载 Nginx，无需再修改 DNS。

`subdomains.conf` 展示了 map 与 upstream 的基础写法，同时保留了未匹配子域的兜底策略。生产环境中，入口脚本会从 `/etc/nginx/ssl-src`
解析真实证书并在 `/etc/nginx/ssl` 内生成标准化链接，便于直接复用 `ssl_certificate` 与 `ssl_certificate_key` 配置。
