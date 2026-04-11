# 企业级 Celery 任务调度：多队列、优先级、隔离与监控

## 1. 为什么需要调度系统

- **削峰填谷**：HTTP 层只负责入队，耗时计算在 Worker 中异步执行，避免阻塞连接与线程。
- **资源可控**：通过队列拆分与 Worker 并发上限，把 CPU/IO 压力限制在可预期范围。
- **可观测**：任务 ID、状态、耗时、重试次数可落库与对接 Flower/Prometheus。

## 2. 队列如何解决资源争抢

- **物理隔离**：`high_priority` / `default` / `low_priority` 使用独立 Kombu `Queue`，Broker（Redis）中为不同 list/stream，互不抢同一条“队头”。
- **Worker 分工**：高优队列由专用 Worker 消费（`-Q high_priority`），训练与离线任务走 `low_priority`，避免批量训练占满预测 Worker。
- **近似优先级抢占**：单 Broker 内无法像 OS 一样中断正在执行的低优任务；通过**独立队列 + 专用高优 Worker** 实现“高优任务始终有可执行槽位”，效果上接近插队。

## 3. 为什么要隔离用户任务

- **公平性**：防止单租户大量提交导致其他租户饥饿。
- **滥用防护**：`QuotaTrackedTask` 用 Redis 槽位限制**单用户并发执行数**（`CELERY_MAX_CONCURRENT_PER_USER`），超限则 `Reject(requeue=True)` 回到队列退避（FIFO 顺序保持）。

## 4. Celery 多队列配置（代码位置）

- 队列与路由：`backend/tasks/queue_config.py`（`CELERY_TASK_QUEUES`、`CELERY_TASK_ROUTES`）。
- 应用合并：`backend/tasks/celery_app.py`（`task_queues`、`task_routes`、`task_default_queue`）。

### 任务 → 队列映射

| 任务 | 队列 |
|------|------|
| `tasks.model_predict_task` | `high_priority` |
| `tasks.analyze_data_task` / `clean_data_task` / `feature_extract_task` | `default` |
| `tasks.scheduled_retrain` / `retrain_on_feedback` / `model_train_async_task` / 生命周期 / Spark 占位 | `low_priority` |
| `tasks.compensation_record` | `compensation` |

## 5. Worker 启动方式（多进程池）

在项目根目录，`PYTHONPATH=.`：

```bash
# 高优：限制并发，避免预测把 CPU 打满
celery -A backend.tasks.celery_app worker -Q high_priority -n worker_high@%h --concurrency=2 --loglevel=info

# 默认：分析/清洗/特征
celery -A backend.tasks.celery_app worker -Q default -n worker_default@%h --concurrency=4 --loglevel=info

# 低优 + 补偿（可同机或分机）
celery -A backend.tasks.celery_app worker -Q low_priority,compensation -n worker_low@%h --concurrency=2 --loglevel=info
```

Beat（周期任务，单实例即可）：

```bash
celery -A backend.tasks.celery_app beat --loglevel=info
```

**说明**：`--concurrency` 即单 Worker 进程内并发协程/子进程数；与 `worker_prefetch_multiplier=1` 配合，避免预取过多任务占满内存。

## 6. 任务分发代码

- 统一封装：`backend/tasks/dispatch.py`（`submit_predict`、`submit_analyze`、`submit_clean`、`submit_feature_extract`、`submit_train_async`）。
- HTTP 示例：`POST /model/predict-async/{filename}`、`POST /model/train-async`（见 `backend/api/model.py`）。
- 业务侧仍可直接 `tasks.xxx.delay()`，路由由 `task_routes` 生效。

## 7. 调度架构说明（文字）

```
[API / 事件] --apply_async--> [Broker: Redis]
                                 |
         +-----------------------+------------------------+
         |                       |                        |
   high_priority            default                low_priority
         |                       |                        |
   worker_high(并发小)    worker_default(并发中)   worker_low(并发小)
         |                       |                        |
   model_predict_task      analyze/clean/feature      train/beat/生命周期
```

失败重试耗尽 → `compensation` 队列 → `compensation_record`（审计/后续告警）。

## 8. 一条完整任务流

1. **提交**：客户端调用 `POST /model/predict-async/xxx` 或 `dispatch.submit_predict(...)` → Broker 在 `high_priority` 入队（FIFO）。
2. **排队**：消息在 Redis 列表中等待；若同用户并发超限，Worker 侧 `Reject(requeue=True)` 将消息放回队尾/队列（退避）。
3. **执行**：`worker_high` 取出任务 → `QuotaTrackedTask` 占槽 → 执行 `model_predict_task` → 释放槽。
4. **完成**：`task_postrun` 更新 `celery_task_runs`（耗时、状态）；结果在 result backend（若需可查 `AsyncResult`）。

## 9. 任务监控与重试

- **表**：`celery_task_runs`（`backend/model/celery_task_run.py`），由 `backend/tasks/monitoring_signals.py` 在 prerun/postrun/failure 写入。
- **重试**：分析/清洗/特征/预测等任务启用 `retry_backoff`、`retry_jitter`；终态失败后由 `QuotaTrackedTask.on_failure` 投递 `compensation_record`。

## 10. 相关环境变量

| 变量 | 含义 |
|------|------|
| `CELERY_MAX_CONCURRENT_PER_USER` | 单用户同时执行的业务任务槽位上限 |
| `CELERY_TASK_MAX_RETRIES` | 默认 `max_retries` 上界（任务装饰器可覆盖） |
