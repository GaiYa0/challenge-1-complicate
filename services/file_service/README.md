# file-service

- 职责：文件元数据写入 **file_db**；对象存 **MinIO**。
- 禁止：连接 `user_db` / `data_db` / `model_db`。
- 用户存在性 / JWT 校验：HTTP 调用 **user-service**（见 `clients/user_service_client.py`）。

依赖环境变量：`USER_SERVICE_URL`、`INTERNAL_API_TOKEN`（与 user-service 一致）。

## Kafka（可选）

- `KAFKA_ENABLED=true`、`KAFKA_BOOTSTRAP_SERVERS`（如 `localhost:19092`）。
- 内部接口：`POST /internal/v1/pipeline/publish`，Header `X-Internal-Token`，Body `{"resource_id":"..."}`，消息 headers 会携带当前请求的 `X-Request-ID`。
