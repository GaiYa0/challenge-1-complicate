# Challenge Demo

全栈演示项目：**FastAPI** 后端（PostgreSQL、Redis、MinIO、Kafka、Neo4j、Celery）+ **Vue 3** 前端。支持 **Docker Compose** 本地/单机部署，以及 **Kubernetes + GitHub Actions** 持续交付。

公开仓库：<https://github.com/GaiYa0/challenge-1-complicate>

---

## 业务功能（当前实现）

- **案件与数据**：案件列表、MinIO 数据导入（CSV / XLS / XLSX）、分析任务与清洗流水。
- **本案表格构图**：从「`dataset=case-{id}`」下的表格解析 `name / counterparty` 或 **财付通 TenpayTrades** 列（用户侧账号名称 → 对手侧账户名称），构建有向边；有金额列时对同向边汇总金额。
- **证据关系图**：`/cases/:caseId/network` 同心圆视图；行为维度为 **资金往来**，边权使用接口返回的 **`weight`**（金额或笔数），与 G6 线宽联动。
- **人物画像与证据链**：`/cases/:caseId/portraits` → 单人画像；纯财付通案件可标记 `fund_only_evidence`，按对手返回 **`fund_counterparty_lines`**（及可选逐笔 `rows`），证据链时间轴优先使用该汇总金额。
- **Neo4j**：`User-[:TRANSFER]` 支持关系属性 **`amount`**；图分析/可视化边权按 `sum(coalesce(r.amount, 1.0))` 聚合（无 `amount` 的旧边等价于按条数计 1）。

更完整的目标架构与数据湖说明见 [`docs/SYSTEM_ARCHITECTURE.md`](docs/SYSTEM_ARCHITECTURE.md)。

---

## 上线方式概览

| 方式 | 适用场景 | 说明 |
|------|----------|------|
| **Docker Compose** | 单机、演示、内网 | 一条命令拉起依赖、后端、Worker，以及 **Nginx + 前端静态资源（`web`）** |
| **自建服务器 + Docker** | 小团队生产 | 同上，配合 HTTPS 反代、替换密钥与镜像仓库 |
| **Kubernetes** | 集群生产 | 使用 `deploy/k8s/`，CI 见 `.github/workflows/k8s-ci-cd.yml` |

---

## 前置要求

- **Docker**：Docker Engine 20+，且已安装 **Docker Compose V2**（`docker compose` 命令可用）
- **（可选）本地前后端分离开发**：Node.js 20+、Python 3.10+、`pip` / `npm`

---

## 方式一：Docker Compose（推荐首次运行）

仓库根目录已提供 `docker-compose.yml`，后端镜像由根目录 `Dockerfile` 构建；环境变量默认读取 **`.env.dev`**（仓库内已带开发占位配置，**生产请务必改为强密钥并改用密钥管理**）。

### 1. 启动

在项目根目录执行（或使用 `run/` 下脚本，见下文「运行脚本」）。**请带上 `--env-file .env.dev`**，以便 Compose 中的 `NEO4J_PASSWORD` 等与 `env_file` 注入后端的一致：

```bash
docker compose --env-file .env.dev up -d --build
```

**前后端分两次启动**（先依赖与 API，再 Nginx）：见 `docker-compose.backend.yml` 与 `docker-compose.frontend.yml`，命令示例见 `run/README.md`。

首次构建可能较慢。全部服务健康后：

- **站点（推荐，前后端同域）**：<http://127.0.0.1:8080> — 由 `web` 服务提供 Vue 构建产物，并将 `/api`、`/ws` 反向代理到后端  
- **API 直连**：<http://127.0.0.1:8000>（调试、OpenAPI 文档）  
- **API 文档**：<http://127.0.0.1:8000/docs>  
- **MinIO 控制台**：<http://127.0.0.1:9001>  

公网或局域网访问时，将上述地址中的 `127.0.0.1` 换为本机 IP 即可；生产环境请在 `web` 前再加 HTTPS 终端（如 Caddy / Nginx / 云 LB）。

### 2. 停止与清理

```bash
docker compose down
```

数据卷默认保留；若需连同数据卷删除：

```bash
docker compose down -v
```

### 3. 前端如何访问后端

- **Docker 一键上线**：使用上述 **8080** 入口即可，无需再跑 `npm run dev`。`frontend/Dockerfile` 会以 `VITE_API_BASE_URL=/api` 构建，由容器内 Nginx（`frontend/docker/nginx-default.conf`）转发到 `backend:8000`。
- **本地开发**：在 `frontend` 目录执行 `npm install` 与 `npm run dev`；默认 `frontend/.env.development` 使用 `VITE_API_BASE_URL=/api`，由 `vite.config.ts` 代理到本机 `127.0.0.1:8000`（须先启动后端）。若改为直连 `http://127.0.0.1:8000`，需后端 `DEBUG=true` 以启用 CORS（见 `backend/main.py`）。
- **仅构建静态资源**：在 `frontend` 目录执行 `npm run build`；自行托管时配置与 `frontend/.env.production` 及 Nginx 示例一致。

**Nginx 示例（静态站 + `/api` 反代）**：构建时使用 `VITE_API_BASE_URL=/api` 与 `VITE_WS_URL` 指向同源 WebSocket 路径（如 `/ws`，需 Nginx 配置 `Upgrade` 头）。示意：

```nginx
server {
    listen 443 ssl;
    root /var/www/challenge-demo/dist;
    location / {
        try_files $uri $uri/ /index.html;
    }
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location /ws {
        proxy_pass http://127.0.0.1:8000/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

实际部署时请替换证书路径、上游地址，并与后端 CORS / 信任代理头策略对齐。

---

## 方式二：运行脚本（快捷命令）

仓库 **`run/`** 目录汇总启动相关 Shell 脚本（macOS / Linux / WSL）。首次使用可赋予执行权限：

```bash
chmod +x run/*.sh
```

| 脚本 | 作用 |
|------|------|
| `run/docker-up.sh` | 构建并后台启动 `docker compose` |
| `run/docker-down.sh` | 停止 Compose 服务 |
| `run/docker-logs.sh` | 跟踪后端日志（可传服务名，默认 `backend`） |
| `run/run.sh` | 统一入口：`./run/run.sh help` 查看子命令 |

其它运维脚本（Kafka topics、SQL 示例等）仍在 **`scripts/`**。

---

## 方式三：Kubernetes 与 CI/CD

1. 根据集群情况修改 `deploy/k8s/` 内镜像地址、域名、Secret 示例（如 `backend-secret.example.yaml`、`postgres-secret.example.yaml`）。
2. 使用 `kubectl apply -k deploy/k8s/`（若使用 Kustomize）或按顺序 apply 清单。
3. GitHub Actions 工作流 **k8s-ci-cd**：推送到 `main` / `master` 时构建并推送 **GHCR** 镜像，并在配置了 `KUBE_CONFIG`（base64 的 kubeconfig）与已存在的 `deployment/backend` 时执行滚动更新。详见 `.github/workflows/k8s-ci-cd.yml`。

---

## 文档导航

- 文档入口：`docs/README.md`
- 运行说明：本 `README.md` + `run/README.md`
- 架构主线：`docs/SYSTEM_ARCHITECTURE.md`
- 接口契约：`docs/API_CONTRACT.md`
- 安全与合规：`docs/COMPLIANCE_SECURITY.md`

---

## 环境变量说明（摘要）

| 类别 | 主要变量 |
|------|----------|
| 数据库 | `DB_HOST`、`DB_PORT`、`DB_USER`、`DB_PASSWORD`、`DB_NAME` |
| Redis | `REDIS_HOST`、`REDIS_PORT` |
| MinIO | `MINIO_ENDPOINT`、`MINIO_ACCESS_KEY`、`MINIO_SECRET_KEY` |
| JWT | `JWT_SECRET`、`JWT_EXPIRE_MINUTES` |
| Neo4j | `NEO4J_URI`、`NEO4J_USER`、`NEO4J_PASSWORD` |
| Kafka | `KAFKA_ENABLED`、`KAFKA_BOOTSTRAP_SERVERS`（Compose 内已由 `docker-compose.yml` 覆盖部分值） |

完整开发占位见根目录 **`.env.dev`**。生产请使用 **`.env.prod`** 或 K8s Secret，**切勿**将真实密钥提交到 Git。

---

## 健康检查与排错

- 后端容器健康检查：`GET http://localhost:8000/live`
- 查看后端日志：`./run/docker-logs.sh` 或 `docker compose logs -f backend`
- 若端口冲突，请修改 `docker-compose.yml` 中的 `ports` 映射。
- ZooKeeper 容器若曾报 **unhealthy**：ZK 3.5+ 默认不开放 `ruok` 四字命令，本仓库已改用 `srvr` + `127.0.0.1` 探测；若仍失败可执行 `docker compose logs zookeeper` 查看 JVM 启动错误。
- **MinIO** 官方镜像内无 `curl`，健康检查使用 **`mc ready`**（凭 `MINIO_ROOT_*`）；若改访问密钥，请保持与 `docker-compose.yml` 中环境变量一致。
- **Neo4j** 健康检查使用 **`cypher-shell` + Bolt 7687**，密码与 `NEO4J_AUTH` / 根目录 `.env` 中的 **`NEO4J_PASSWORD`** 一致；首次启动 JVM 较慢，已加大 `start_period`。

---

## 登录与演示账号

- **`DEBUG=true`（如 `.env.dev`）**：应用启动时若数据库中**尚无**用户名为 `admin` 的记录，会自动创建 **`admin` / `admin`**、角色 `admin`。重启后端即可生效。
- **查看已有账号**：请在数据库中直接查询 `users` 表。
- **`DEBUG=false`（生产）**：不会自动建号，请自行在库中创建用户并禁用弱口令。

---

## 技术栈速览

- 后端：FastAPI、SQLAlchemy、Celery、Kafka、Redis、PostgreSQL、MinIO、Neo4j  
- 前端：Vue 3、Vite、TypeScript、Pinia、Element Plus、ECharts  

---

## 许可证

以仓库内 LICENSE 文件为准（若未包含则由项目所有者自行补充）。
