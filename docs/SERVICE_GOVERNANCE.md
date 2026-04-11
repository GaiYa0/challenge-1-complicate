# 服务治理体系设计

## 1. 为什么必须 API 网关

- **统一入口**：客户端只面对一个域名与 TLS 证书，隐藏后端多端口、多实例拓扑。
- **横切能力集中**：认证（JWT）、限流、审计、CORS、请求大小限制在网关一次完成，避免每个服务重复实现且不一致。
- **协议与路由演进**：可在网关做路径版本化（`/user/v1`）、灰度与重定向，而不强迫所有微服务同时升级。
- **观测一致性**：在网关生成或校验 `X-Request-ID`，作为整条链路的关联键，便于日志与追踪系统汇总。

本仓库实现：`services/gateway/main.py`（FastAPI），将 `/user` 转发至 user-service，`/file` 转发至 file-service，并对除白名单外的请求校验 **Bearer JWT**（密钥须与 user-service 的 `JWT_SECRET` 一致）。

## 2. 同步 vs 异步通信

| 维度 | 同步 HTTP | 异步 Kafka |
|------|-----------|------------|
| 耦合 | 调用方等待响应，超时与重试语义清晰 | 发布方不等待消费者完成 |
| 一致性 | 强依赖下游可用性 | 可削峰、可重放（视配置） |
| 适用 | 查询、强实时校验、短事务编排 | 数据处理、模型训练等长耗时、可多订阅者 |
| 失败 | 直接反馈 4xx/5xx 或降级 | 依赖消费者幂等与死信队列策略 |

本仓库示例：

- **HTTP**：`services/user_service/api/chain_demo.py`（user → file `/health`），`services/common/http_resilient.py`（timeout + 重试 + 可选熔断）。
- **Kafka**：`services/file_service/api/pipeline_events.py` 发布；`services/data_service/kafka_worker.py` 消费；`services/common/kafka_bus.py` 在消息 headers 携带 `request_id`。模型训练异步投递示例：`python -m services.model_service.publish_train_demo`（topic `ms.model.train`）。

## 3. 为什么要链路追踪（request_id）

- **跨服务排障**：没有关联 ID 时，只能凭时间戳猜测同一请求在 user / file / data 的日志片段。
- **性能分析**：可统计「网关 → user → file」各段耗时（配合 APM 更佳）。
- **审计合规**：同一业务操作在多服务留痕时，可用 `request_id` 串联。

实现要点：

1. 网关中间件 `RequestIdMiddleware`：读取或生成 `X-Request-ID`，写入 `contextvars` 与响应头。
2. 下游 HTTP 调用前 `ensure_request_id_header`：把当前上下文中的 ID 写入出站请求头。
3. 日志 `JsonLogFormatter`：每条日志带 `request_id`、`service` 字段，便于 Filebeat 投递 **ELK**。

## 4. 组件一览

| 能力 | 位置 |
|------|------|
| 注册表（简单版） | `services/gateway/config/registry.yaml`，环境变量 `USER_SERVICE_URL` / `FILE_SERVICE_URL` 优先 |
| JWT 网关 | `services/gateway/auth/jwt_gate.py` |
| 反向代理 + 熔断降级 | `services/gateway/api/proxy.py` + `services/common/http_resilient.py` + `services/common/circuit.py` |
| request_id + JSON 日志 | `services/common/tracing.py`、`services/common/logging_setup.py` |
| Kafka 发布 | `services/common/kafka_bus.py` |
| HTTP 重试（同步客户端） | `services/file_service/clients/user_service_client.py` |

## 5. ELK 汇总建议

- 所有服务 stdout 已输出 **单行 JSON**（字段含 `@timestamp`、`level`、`service`、`request_id`、`message`）。
- 使用 **Filebeat** `json` 解析模式采集容器或进程日志，输出到 **Logstash/Elasticsearch**；Kibana 按 `request_id` 过滤即可还原调用链。

## 6. 一条完整调用链（文字）

```
客户端
  → [POST /user/auth/login]（无 JWT）→ user-service 签发 token
客户端带 Authorization + X-Request-ID（可选）
  → [GET /user/v1/chain/file-health] → 网关校验 JWT
  → 转发 GET {USER_URL}/v1/chain/file-health（带 X-Request-ID）
  → user-service 校验 token 后 HTTP 调用 file-service /health（再次附带 X-Request-ID）
  → file-service 返回 JSON（含 request_id）
  → 经网关回到客户端
```

Kafka 分支（异步）：

```
file-service POST /internal/v1/pipeline/publish（带 X-Request-ID）
  → publish_event 在 Kafka headers 写入 request_id
  → data-service kafka_worker 消费并打印结构化日志（含 request_id）
```

## 7. 运行片段

```bash
# 终端 1：user-service
PYTHONPATH=. uvicorn services.user_service.main:app --port 8001

# 终端 2：file-service
PYTHONPATH=. uvicorn services.file_service.main:app --port 8002

# 终端 3：网关（JWT_SECRET 与 user-service 一致）
export JWT_SECRET=change-me-in-production
PYTHONPATH=. uvicorn services.gateway.main:app --port 8000

# Kafka（可选）
docker compose -f docker-compose.kafka.yml up -d
export KAFKA_ENABLED=true KAFKA_BOOTSTRAP_SERVERS=localhost:19092
PYTHONPATH=. python -m services.data_service.kafka_worker
```

白名单（网关不校验 JWT）：`POST /user/auth/login`、`GET /user/health`、`GET /file/health`、`OPTIONS *`、网关 `GET /health`。
