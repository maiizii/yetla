
# yet.la 管理平台

一个运行在 Linux 服务器上的轻量级管理后台，用来集中管理 `*.yet.la` 下的二级域名解析和短链接跳转规则。项目默认配合 Cloudflare 进行 DNS 解析，由 Nginx 负责 HTTP 入口。

二级域名及短链接管理平台，目前仓库处于规划阶段。

## 快速导航
- [项目入门指引](docs/ONBOARDING.md)：了解业务背景、推荐的目录规划以及上手建议。

## 功能概览

- 📚 **二级域名管理**：维护业务子域、临时测试域、静态资源域等记录。
- 🔗 **短链接转发**：统一管理 yet.la 短链与目标 URL 的映射，支持批量导入与版本控制。
- 🛡️ **安全与审计**：记录重要操作、变更历史，方便回溯。
- ⚙️ **自动化配置**：生成可供 Nginx/其他服务使用的配置文件，减少手工操作。

> 本仓库目前处于初始化阶段，尚未包含完整的后端/前端代码，欢迎在 README 的基础上逐步完善实现。

## 系统架构建议

```
+---------------------+           +-------------------------+
|  yet.la 管理平台后端 | <-------> |  数据库 (PostgreSQL/...) |
+---------------------+           +-------------------------+
          |                                   ^
          v                                   |
+---------------------+           +-------------------------+
|  配置生成/同步模块   | --------> |  Nginx 配置或 Cloudflare  |
+---------------------+           +-------------------------+
```

- **后端服务**：提供 RESTful API（建议使用 Python/FastAPI、Node.js/NestJS 或 Go）。
- **数据库**：存储域名记录、短链接映射、操作日志等。
- **配置同步**：将数据库中的配置同步到 Nginx 或调用 Cloudflare API。
- **前端界面**（可选）：为管理员提供可视化界面，亦可只提供命令行工具。

## 前置条件

1. **域名解析**：已在 Cloudflare 将 `*.yet.la` 指向当前服务器。
2. **服务器环境**：Linux (推荐 Ubuntu 20.04 及以上)，已安装 Nginx。
3. **依赖工具**：Git、Docker（可选）、Make（可选）。
4. **SSL 证书**：建议通过 Cloudflare 或 ACME 自动签发。

## 快速开始

> 以下步骤仅作为参考，具体命令需根据后续实现的语言/框架调整。

```bash
# 1. 克隆仓库
$ git clone git@github.com:your-org/yetla.git
$ cd yetla

# 2. 创建环境变量文件
$ cp .env.example .env
#   - 填写 Cloudflare API Token / Nginx 配置路径等信息

# 3. 启动开发环境（示例：Docker Compose）
$ docker compose up --build

# 4. 运行数据库迁移、种子数据
$ docker compose exec app python manage.py migrate
$ docker compose exec app python manage.py loaddata fixtures/*.json
```

## 部署建议

1. **CI/CD**：使用 GitHub Actions 或 GitLab CI 检查代码质量、运行测试、生成配置。
2. **自动同步**：提交合并后触发部署脚本，将新配置推送到 Nginx 并重载服务：
   ```bash
   $ sudo systemctl reload nginx
   ```
3. **备份策略**：定期备份数据库与配置文件。
4. **监控告警**：引入 Prometheus + Grafana 或 Cloudflare Analytics，及时掌握请求情况。

## 开发计划（Roadmap）

- [ ] 设计数据库 schema（域名记录、短链接、审计日志）
- [ ] 实现基础 CRUD API
- [ ] 编写前端页面或命令行交互工具
- [ ] 集成 Cloudflare API
- [ ] 自动化部署与配置同步

## 贡献指南

1. Fork 本仓库并创建特性分支。
2. 提交前请运行全部测试并通过 Lint 检查。
3. 提交 PR 时请附上修改说明、测试截图或日志。

欢迎在 Issue 中提出需求或建议，让 yet.la 的二级域名和短链接管理更加高效！


