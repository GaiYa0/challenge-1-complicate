# task-service

- 职责：Celery worker/beat、任务编排、重试与状态（可选独立 `task_db` 或仅 Redis）。
- 禁止：为“省事”直连其他服务的业务库。
- 集成：通过 HTTP 或 broker 消息调用 **data-service**、**model-service** 等；鉴权可调用 **user-service** 内部校验接口。
