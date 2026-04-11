# model-service

- 职责：模型训练、在线/离线预测；读写 **model_db**。
- 禁止：直连 `user_db` / `file_db` / `data_db`。
- 输入：经 HTTP 或消息从 **data-service** 获取特征产物 ID / 路径；由 **task-service** 编排长任务。

## Kafka 训练事件示例

```bash
export KAFKA_BOOTSTRAP_SERVERS=localhost:19092
PYTHONPATH=. python -m services.model_service.publish_train_demo
```
