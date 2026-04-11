# 微服务拆分与数据库隔离设计

## 1. 微服务拆分图（文字）

```
                    [API 网关 / BFF]
                           |
     +----------+--------+---------+----------+
     |          |        |         |          |
 user-svc   file-svc  data-svc  model-svc  task-svc
 (user_db) (file_db) (data_db) (model_db) (Redis/Rabbit 等)
     ^          |        |         |
     |          +--------+---------+---- HTTP / 消息（禁止跨库直连）
     +---------------- 各服务只连自己的库 ----------------+
```

**task-service**：负责任务编排（Celery worker/beat、队列），通过消息或 HTTP 触发 data / model 等；不持有 `user_db` 等业务库写权限。

## 2. 各服务职责

| 服务 | 职责 | 数据库 / 外部 |
|------|------|----------------|
| user-service | 用户、登录、JWT 签发与内部校验接口 | **user_db** |
| file-service | 上传、元数据、MinIO | **file_db** + MinIO |
| data-service | 清洗、特征工程 | **data_db** |
| model-service | 训练、预测 | **model_db** |
| task-service | Celery 调度、异步流水线 | 队列 broker；可选独立 `task_db` 存任务状态 |

## 3. 为什么要微服务

- **独立演进**：训练与预测变更频繁，不应与用户表结构强耦合发布。
- **伸缩粒度**：预测 QPS 高时可单独扩容 model-service。
- **故障隔离**：文件管道异常不应拖垮登录。
- **团队边界**：按领域拆分代码与发布单元，降低合并冲突与回归范围。

## 4. 为什么必须数据库隔离

- **边界即契约**：跨服务读对方表会让 schema 变更变成“隐式公共 API”，任何一方迁移都会炸一片。
- **独立事务与连接池**：避免一个慢查询占满共享库连接。
- **合规与最小权限**：用户数据与文件元数据可分别备份、审计、脱敏。
- **禁止跨服务直连数据库**后，唯一集成方式是 **HTTP / 消息**，便于版本化、重试与观测。

## 5. 单体 vs 微服务

| 维度 | 单体 | 微服务（本设计） |
|------|------|------------------|
| 部署 | 一次发布整块应用 | 按服务独立发布 |
| 数据 | 常共享同一数据库 | **每服务独立库** |
| 调用链 | API → Service → DB | Service A → **HTTP/消息** → Service B → B 的 DB |
| 复杂度 | 运行时简单，长期耦合高 | 运维与分布式事务更难，领域边界更清晰 |

## 6. 优先拆分顺序

1. **user-service**（认证稳定、依赖少）
2. **file-service**（依赖 user 的 HTTP 校验）
3. **data-service**（依赖 file 元数据或事件）
4. **model-service**（依赖特征与训练数据，最复杂）
5. **task-service**（编排以上异步步骤；可与 4 并行规划，实现往往最后固化）

## 7. 服务间调用示例（HTTP）

- **file-service** 在处理上传前，用 `X-Internal-Token` 调 user-service：`POST /internal/v1/token/validate`。
- **data-service** 任务完成后发消息或回调 **task-service**；由 task-service 再触发 model-service，避免 data 直连 model_db。

代码示例见仓库：

- `services/user_service/api/internal.py` — 对内 HTTP API
- `services/file_service/clients/user_service_client.py` — 客户端调用

## 8. user-service 目录约定

```
services/user_service/
├── api/
├── service/
├── repository/
├── model/
├── schema/
├── core/
└── main.py
```

本地运行（项目根为 `PYTHONPATH`）：

```bash
export DATABASE_URL=postgresql://user:password@localhost:5432/user_db
uvicorn services.user_service.main:app --host 0.0.0.0 --port 8001
```

## 9. 数据库初始化（示例）

在同一 Postgres 实例上创建逻辑库（仍属“独立数据库”）：

```sql
CREATE DATABASE user_db;
CREATE DATABASE file_db;
CREATE DATABASE data_db;
CREATE DATABASE model_db;
```

各服务连接字符串仅指向自己的库名。
