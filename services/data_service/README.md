# data-service

- 职责：数据清洗、特征工程；读写 **data_db**。
- 禁止：直连 `user_db` / `file_db` / `model_db`。
- 输入：通过 HTTP 向 **file-service** 拉取元数据，或消费 **task-service** 发出的消息（对象键、数据集版本等）。

## Kafka 消费示例

治理相关说明见 `docs/SERVICE_GOVERNANCE.md`。消费 `ms.data.pipeline`：

```bash
export KAFKA_BOOTSTRAP_SERVERS=localhost:19092
PYTHONPATH=. python -m services.data_service.kafka_worker
```
