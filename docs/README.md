# 文档总览（docs）

本目录已按“运行主链路 + 架构主链路”整合，优先阅读以下文档：

## 核心文档

- `SYSTEM_ARCHITECTURE.md`：全局系统架构（数据湖、流批、模型、部署视图）
- `API_CONTRACT.md`：前后端接口契约与统一响应规范
- `BACKEND_FOUNDATION.md`：后端基础能力、数据模型与契约
- `FRONTEND_ARCHITECTURE.md`：前端工程结构、状态与 API 约束
- `COMPLIANCE_SECURITY.md`：合规、安全、审计与导出审批
- `COST_AND_LIFECYCLE.md`：冷热分层、成本与生命周期策略
- `CELERY_SCHEDULING.md`：异步任务调度与队列治理

## 扩展文档

- `MICROSERVICES_DESIGN.md`：微服务拆分与数据库隔离设计（演进方向）
- `SERVICE_GOVERNANCE.md`：网关、调用治理、链路追踪与可观测

## 兼容入口（已整合）

- `DOCKER.md`：运行说明已并入仓库根 `README.md` 与 `run/README.md`
- `PLATFORM_ARCHITECTURE_REFACTOR.md`：重构建议已并入核心架构文档
