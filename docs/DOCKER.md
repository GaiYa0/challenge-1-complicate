# Docker Compose 一键启动

## 启动命令

在项目根目录（含 `docker-compose.yml` 与 `Dockerfile`）执行：

```bash
docker compose up -d --build
```

（若使用旧版 Compose 插件，可执行：`docker-compose up -d --build`。）

停止：

```bash
docker compose down
```

查看日志：

```bash
docker compose logs -f backend
```

---

## 服务与端口（宿主机）

| 服务 | 端口 | 说明 |
|------|------|------|
| **backend** | **8000** | FastAPI：`http://localhost:8000/docs` |
| **postgres** | **5432** | PostgreSQL |
| **redis** | **6379** | Redis |
| **minio** | **9000** | S3 API；**9001** 为控制台 |
| **kafka** | **9092** | 对宿主机的 PLAINTEXT（容器内 broker 间为 `kafka:29092`） |
| **zookeeper** | 2181 | 未映射到宿主机，仅在 `app-net` 内供 Kafka 使用 |
| **neo4j** | **7687** Bolt；**7474** Browser | 图谱（应用 lifespan 依赖） |
| **celery-worker** | — | 异步任务 |
| **kafka-consumer** | — | 事件管线消费 |

---

## 环境变量（`.env.dev`）

Compose 通过 `env_file: .env.dev` 注入变量，并对 **数据库 / Redis / MinIO / Neo4j / Kafka** 使用容器内主机名覆盖 `.env.dev` 中的 `localhost`，见 `docker-compose.yml` 中 `backend` / `celery-worker` / `kafka-consumer` 的 `environment` 段。

---

## 数据卷（持久化）

- `postgres_data` → PostgreSQL 数据目录  
- `minio_data` → MinIO 对象存储  
- `kafka_data` → Kafka broker 日志  
- `zookeeper_data` / `zookeeper_log` → ZooKeeper 状态  
- `neo4j_data` → Neo4j 图数据  

---

## 目录结构（与容器的关系）

```
challenge demo/           # 构建上下文（COPY 到镜像 /app）
├── Dockerfile
├── docker-compose.yml
├── main.py               # uvicorn main:app 入口
├── requirements.txt
├── .env.dev              # 注入容器 + 供 pydantic 读取
├── backend/              # 应用包
│   └── main.py           # FastAPI app 定义
└── docs/
    └── DOCKER.md         # 本文档
```

镜像内工作目录为 `/app`，`PYTHONPATH=/app`，与本地 `PYTHONPATH=.` 运行方式一致。
