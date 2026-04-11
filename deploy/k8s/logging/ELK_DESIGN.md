# 日志收集（ELK）设计说明

## 目标

将 **API / Worker / Kafka Consumer** 的容器 stdout（JSON 行日志）汇聚到 Elasticsearch，经 Logstash 解析字段后，在 Kibana 检索与仪表盘展示。

## 推荐拓扑（进阶）

1. **Filebeat**（DaemonSet）：挂载 `varlogcontainers`，按 `namespace=challenge-demo` 过滤 Pod。
2. **Logstash**（Deployment）：接收 beats → 解析 `request_id`、`user_id`、`latency_ms` → 输出到 ES。
3. **Elasticsearch**（StatefulSet + PVC）：三节点集群（生产）；开发可单节点。
4. **Kibana**（Deployment）：连接同一 ES 集群。

## 与 Prometheus 分工

| 系统 | 用途 |
|------|------|
| Prometheus + Grafana | 指标：CPU、内存、QPS、错误率、HPA |
| ELK | 日志：请求链路、异常栈、审计与安全事件 |

## 实施提示

- 使用 **Elastic Cloud on Kubernetes (ECK)** 或官方 Helm chart 降低运维成本。
- 敏感字段（JWT、密码）在 Logstash 中 **drop** 或脱敏。
- 保留策略：热索引 7 天、温索引 30 天、冷归档按需。

本仓库仅保留设计文档；完整 Helm 值文件可按集群规模另开仓库维护。
