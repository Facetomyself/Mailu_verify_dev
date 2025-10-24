# Mailu验证码接码平台

## 项目概述
Mailu验证码接码平台通过调用Mailu的REST API与SMTP能力，按需创建临时邮箱并实时抓取验证码，提供自助式仪表板与标准化API，适合验证码接码、注册流程验证等自动化场景。

## 核心特性
- FastAPI异步后端封装临时邮箱生命周期与验证码查询接口。
- Celery异步任务结合Redis队列，实现邮件轮询、验证码提取与统计刷新。
- Redis缓存保存验证码、邮箱元数据与加锁信息，降低数据库压力。
- MySQL持久化邮箱和验证码记录，支持审计与统计分析。
- Nginx统一暴露前后端入口，Docker Compose一键部署。

## 架构组件
- `backend`：FastAPI应用，提供REST接口、模板渲染与数据库访问。
- `celery_worker`：Celery任务节点，处理邮箱创建、邮件扫描、验证码解析等后台任务。
- `celery_beat`：Celery调度器，周期触发任务队列。
- `mysql`：持久化存储，记录邮箱、验证码、域名与统计数据。
- `redis`：缓存与消息队列，支撑验证码缓存、任务分发、限流锁。
- `nginx`：反向代理与静态资源托管，统一外部访问入口。
- `frontend`：Jinja2模板与静态资源，提供仪表板界面。
- `analyze_swagger.py` 与 `swagger.json`：分析Mailu官方API的工具与文档快照。

## 目录结构
```text
.
├── backend/
│   └── app/
│       ├── celery/           # Celery应用与任务
│       ├── models/           # SQLAlchemy模型与数据库会话
│       ├── services/         # Mailu客户端、邮件发送、缓存服务
│       ├── utils/            # 通用工具函数
│       └── main.py           # FastAPI入口
├── frontend/
│   ├── templates/            # 仪表板模板
│   └── static/               # CSS/JS等静态资源
├── mysql/
│   └── init.sql              # 初始建表脚本
├── nginx/
│   └── nginx.conf            # 反向代理配置
├── start.sh                  # 一键启动脚本
├── docker-compose.yml        # 容器编排
├── requirements.txt          # Python依赖清单
├── swagger.json              # Mailu API描述
└── analyze_swagger.py        # Swagger分析脚本
```

## 快速开始

### 1. 准备运行环境
- Docker 20.10 或以上版本
- Docker Compose 2.0 或以上版本
- Python 3.10+（仅在本地开发模式需要）
- 预留端口：8000、30001、3306、6379

### 2. 配置环境变量
```bash
cp .env.example .env
vim .env
```
至少补充 Mailu 管理端点 `API_URL` 与授权令牌 `API_TOKEN`，并根据实际情况调整数据库与SMTP参数。

### 3. 一键启动（推荐）
```bash
chmod +x start.sh
./start.sh
```
`start.sh` 会检查依赖、创建必要目录、构建镜像并通过 `docker-compose up -d --build` 启动全部服务。首次运行完成后可直接访问仪表板与接口。

如需手动控制容器生命周期，可直接执行：
```bash
docker-compose up -d --build
docker-compose ps
```

### 4. 手动启动（开发模式）
1. 启动依赖组件（可使用 Docker 保持与生产一致）：
   ```bash
   docker-compose up -d mysql redis
   ```
2. 创建虚拟环境并安装依赖：
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. 启动 FastAPI 应用：
   ```bash
   uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
   ```
4. 启动 Celery 任务与调度：
   ```bash
   celery -A backend.app.celery worker --loglevel=info --concurrency=4 -Q email_check,code_extract,celery
   celery -A backend.app.celery beat --loglevel=info
   ```
5. 前端模板通过 FastAPI 提供，可在浏览器访问 `http://localhost:8000` 或通过 Nginx 入口访问。

停止开发模式时可执行 `docker-compose down` 关闭依赖服务。

## 运行入口
- 仪表板界面：`http://localhost:30001`
- 接口文档：`http://localhost:30001/docs`
- 健康检查：`http://localhost:30001/health`
- 原生 FastAPI 服务（开发模式）：`http://localhost:8000`

## 环境变量说明
| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `API_URL` | 无 | Mailu 管理 API 基础地址，需指向 Mailu 实例的 `/api/v1/`。 |
| `API_TOKEN` | 无 | Mailu API 访问令牌，需具备创建用户与管理域名权限。 |
| `DEFAULT_DOMAIN` | `example.com` | 未指定域名时生成临时邮箱使用的默认域名。 |
| `DATABASE_URL` | `mysql+pymysql://user:password@localhost/mailu_codes` | SQLAlchemy 数据库连接串，容器启动时会根据 `.env` 自动覆盖。 |
| `MYSQL_ROOT_PASSWORD` | `rootpassword` | MySQL 容器 root 密码。 |
| `MYSQL_DATABASE` | `mailu_codes` | 应用使用的数据库名称。 |
| `MYSQL_USER` | `mailu_user` | 应用数据库用户。 |
| `MYSQL_PASSWORD` | `mailu_password` | 应用数据库用户密码。 |
| `REDIS_HOST` | `redis` | Redis 主机地址。 |
| `REDIS_PORT` | `6379` | Redis 端口。 |
| `REDIS_DB` | `0` | Redis 数据库索引，缓存与队列的默认选择。 |
| `REDIS_PASSWORD` | 空 | Redis 认证密码，如启用需同步更新 Celery 配置。 |
| `CELERY_BROKER_URL` | `redis://redis:6379/1` | Celery 消息代理地址，默认使用 Redis。 |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/2` | Celery 结果存储地址。 |
| `SMTP_SERVER` | `mail.zhangxuemin.work` | SMTP 发件服务器地址。 |
| `SMTP_PORT` | `465` | SMTP 端口。 |
| `SMTP_USE_SSL` | `true` | 是否启用 SSL。 |
| `SMTP_USE_TLS` | `false` | 是否启用 STARTTLS。 |
| `TZ` | `Asia/Shanghai` | 容器时区设置。 |

修改 `.env` 后，重启相关服务即可生效。

## Celery 任务与调度
- `check_emails`：轮询所有活跃临时邮箱，触发单邮箱扫描任务。
- `check_single_email`：连接 Mailu 邮箱检查新邮件。
- `extract_codes`：解析邮件内容中的验证码并写入数据库与 Redis。
- `create_temp_email_task`：调用 Mailu API 创建临时邮箱并记录生命周期信息。
- `cleanup_expired`：清理过期邮箱与验证码，保持数据库整洁。
- `sync_mailu_data`：定期同步 Mailu 侧数据并触发统计刷新。
- `update_stats_cache`：刷新统计指标缓存，供仪表板查询。

`celery_beat` 默认配置了 30 秒邮件扫描、5 分钟数据同步和 24 小时清理任务，可在 `backend/app/celery/__init__.py` 中调整。

## API 概览
- REST 接口通过 FastAPI 暴露，完整定义可在运行实例的 `/docs` 与 `/openapi.json` 查看。
- `POST /api/emails`：创建临时邮箱。
  ```bash
  curl -X POST "http://localhost:30001/api/emails" \
    -H "Content-Type: application/json" \
    -d '{"expire_hours": 24}'
  ```
- `GET /api/emails/{email}/code`：查询指定邮箱的最新验证码。
  ```bash
  curl "http://localhost:30001/api/emails/test@example.com/code"
  ```
- `GET /api/stats`：获取当前统计指标。
- `GET /`：返回可视化仪表板。

需要批量或二次开发时，可使用 `analyze_swagger.py` 脚本分析 `swagger.json` 中的 Mailu 原生端点，提升集成效率。

## 数据与缓存
- MySQL 保存邮箱、验证码、域名及统计信息；初始化结构可参考 `mysql/init.sql`。
- Redis 存储验证码缓存（默认 1 小时）、邮箱元数据缓存、任务锁与统计数据（默认 5 分钟）。

## 日志与排障
- 查看所有服务日志：`docker-compose logs -f`
- 查看单个服务日志：`docker-compose logs -f backend`
- 监控资源：`docker stats`
- 检查数据库状态：`docker-compose exec mysql mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" $MYSQL_DATABASE`
- 检查 Redis 状态：`docker-compose exec redis redis-cli ping`
- 如果健康检查失败，确认环境变量配置、数据库连接与 Mailu API 可达性。

## 开发与测试
- 新增业务逻辑请保持模块化结构，按职责放置于 `backend/app/services`、`backend/app/domain` 等子目录。
- 推荐在 `tests/` 目录下编写 `pytest` 用例：
  ```bash
  pytest tests/
  ```
- 对接 Mailu API 的新行为或兼容性修改请同步更新 `swagger.json`（可使用官方 OpenAPI 文档重新导出）。

## 贡献指南
欢迎通过 Issue 与 Pull Request 提交改进。提交前请确认：
- 文档与 `.env.example` 已同步更新。
- 新增依赖已经写入 `requirements.txt`。
- 相关功能通过手动验证及自动化测试。

## 许可证
本项目采用 MIT License，详情请参阅仓库根目录的许可证文件。
