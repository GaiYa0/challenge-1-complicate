# 企业级资源与成本优化：存储 / 计算 / 缓存

## 1. 冷热数据分层方案

| 层级 | 时间窗口 | 访问特征 | 存储介质 | 元数据 |
|------|-----------|----------|----------|--------|
| **Hot** | 最近 7 天 | 高频 | Redis 缓存文件元数据摘要 + MinIO 原始对象 | PostgreSQL `files` 行完整 |
| **Warm** | 7～30 天（相对创建时间） | 偶发 | 仅 PostgreSQL + MinIO 标准桶对象 | 同上，`lifecycle_tier=warm` |
| **Cold** | 创建超过 30 天 | 极少 | MinIO **冷桶**存 `gzip`（可选 Parquet）对象 | PG 保留索引字段 + `cold_object_name` / `archive_format` |

自动迁移由 Celery Beat 调度：`lifecycle_demote_hot_to_warm`、`lifecycle_archive_warm_to_cold`（见 `backend/tasks/lifecycle_tasks.py`）。

## 2. 为什么要冷热分层

- **成本**：SSD/Redis 与标准对象存储单价差异大；历史数据占容量大头却几乎不被读取。
- **性能**：热数据走内存/Redis，降低 PG 与 MinIO 的随机读放大。
- **可运维**：分层后容量规划、备份策略可按 tier 分级（冷数据可降低副本或走归档存储类）。

## 3. 为什么不能全部用 Redis

- **内存成本**：全量数据进 Redis 会导致内存线性爆炸，单位 GB 成本通常高于对象存储。
- **持久化模型**：Redis 更适合缓存/会话/排行榜；对象与审计轨迹仍应以 PG + 对象存储为权威。
- **查询能力**：复杂条件检索、关联与合规审计更适合关系型数据库与数仓，而不是 KV。

## 4. 成本优化如何影响系统设计

- **接口路径**：读文件统一走 `storage_service.read_file_bytes`，内部根据 `lifecycle_tier` 选择桶与解压，避免调用方散落判断逻辑。
- **计算路径**：按输入体量在 `compute_router` 中选择同步 / Celery /（预留）Spark，避免小任务排队与大任务阻塞 API。
- **缓存路径**：L1 进程内 → L2 Redis → L3 PG，命中率与失效策略必须与生命周期迁移协调（迁移后主动删热点键）。
- **可观测性**：HTTP 与 Celery 任务写入 `cost_metrics`（或日志兜底），支撑按用户/路由/任务做容量与 SLA 复盘。

## 5. 数据生命周期流程（端到端）

1. **上传**：对象写入 MinIO 标准桶；`files` 插入，`lifecycle_tier=hot`，`warm_month_key=YYYY-MM`；列表缓存失效。
2. **读取/分析**：`read_file_bytes` 更新 `last_accessed_at` / `access_count`，并向 Redis 写入 7 天热元数据；分析结果走现有 `read_through_json`（结果缓存）。
3. **定时（>7 天）**：Beat 触发 `lifecycle_demote_hot_to_warm`，清除热 Redis 键，tier 标记为 `warm`。
4. **定时（>30 天）**：`lifecycle_archive_warm_to_cold` 将对象压缩写入 `cold-data` 桶，更新 `cold_object_name` 与 `archive_format`，tier=`cold`；读取时自动 `gzip` 解压。
5. **删除**：删除 PG 行并尽力删除标准桶与冷桶对象（见 `storage_service.delete_object_for_row`）。

## 6. 分表与字段优化说明

- **分表**：生产建议按 `warm_month_key`（`YYYY-MM`）做 PostgreSQL 原生分区或分表路由；仓库提供示例脚本 `scripts/partition_files_monthly.sql`（可按环境调整）。
- **大对象**：冷层禁止裸存超大 CSV，统一 `gzip_csv` 或（可选）`parquet`（需 PyArrow/Pandas 环境）。

## 7. 存量库迁移 SQL

- 列变更：`scripts/alter_files_lifecycle.sql`
- 分区设计参考：`scripts/partition_files_monthly.sql`

## 8. 相关代码索引

| 能力 | 位置 |
|------|------|
| 模型字段 / 索引 | `backend/model/file.py` |
| 生命周期与 Redis 热键 | `backend/service/lifecycle_service.py` |
| 读路径 / 删除双桶 | `backend/service/storage_service.py`、`backend/infra/minio_client.py` |
| Celery 迁移任务 | `backend/tasks/lifecycle_tasks.py` |
| Beat 调度 | `backend/tasks/celery_app.py` |
| L1/L2/L3 缓存示例 | `backend/infra/tiered_cache.py` |
| 计算分级 | `backend/service/compute_router.py` |
| 成本指标 | `backend/model/cost_metric.py`、`backend/tasks/cost_tasks.py`（由 `backend/main.py` 访问日志中间件异步投递） |
| Spark 预留 | `backend/tasks/spark_placeholder.py` |
