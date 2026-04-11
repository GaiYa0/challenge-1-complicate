# 生产级部署架构（Kubernetes + CI/CD）说明

## 一、系统部署架构图（文字版）

```
                    [ 用户 / 公网 ]
                           │
                    ┌──────▼──────┐
                    │  Ingress    │  TLS / 路由 / 限流（Nginx 等）
                    │  Controller │
                    └──────┬──────┘
                           │
              ┌────────────▼────────────┐
              │   Service: backend      │ ClusterIP :8000
              └────────────┬────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   ┌────▼────┐        ┌─────▼─────┐      ┌─────▼─────┐
   │ backend │        │ backend   │      │ backend   │  HPA 按 CPU 扩缩
   │ Pod     │ ...    │ Pod       │      │ Pod       │  PDB 保证可用下限
   └────┬────┘        └─────┬─────┘      └─────┬─────┘
        │                   │                  │
        └─────────┬─────────┴─────────┬────────┘
                  │                 │
     ┌────────────▼──┐   ┌──────────▼─────────┐   ┌─────────────┐
     │ Service:       │   │ Service: redis     │   │ Service:    │
     │ postgres       │   │                    │   │ minio       │
     └────────┬────────┘   └──────────┬─────────┘   └──────┬──────┘
              │                       │                    │
     ┌────────▼────────┐     ┌────────▼────────┐   ┌───────▼────────┐
     │ PostgreSQL      │     │ Redis            │   │ MinIO          │
     │ + PVC + CronJob │     │                  │   │ + PVC          │
     │   (逻辑备份)     │     │                  │   │ (纠删码集群可 │
     └─────────────────┘     └──────────────────┘   │  选生产扩展)   │
                                                    └────────────────┘
     ┌─────────────────────────────────────────────────────────────┐
     │ Kafka + ZooKeeper（事件总线；生产建议 Strimzi / 云托管）      │
     └─────────────────────────────────────────────────────────────┘

     ┌──────────────┐     ┌──────────────┐
     │ Prometheus   │────▶│ Grafana      │  指标：CPU/内存/QPS/错误率
     └──────────────┘     └──────────────┘

     （日志）Filebeat → Logstash → Elasticsearch → Kibana — 见 logging/ELK_DESIGN.md
```

---

## 二、一条完整部署链路

1. **开发提交**代码到 `main` → 触发 **GitHub Actions**。  
2. **构建** `Dockerfile` 镜像 → 推送到 **GHCR**（`ghcr.io/<owner>/challenge-demo:<sha>`）。  
3. **kubectl**（使用仓库 Secret `KUBE_CONFIG`）对集群执行 **`kubectl set image`**，滚动更新 `Deployment/backend`。  
4. **Ingress** 将公网流量导入 **Service/backend**；**HPA** 根据 CPU 自动增减 Pod。  
5. **Prometheus** 拉取 `/metrics`；**Grafana** 做大盘；**CronJob** 周期性 **pg_dump** 备份 PostgreSQL。

---

## 三、CI/CD 流程设计（任务 4）

| 阶段 | 动作 | 产出 |
|------|------|------|
| Trigger | push `main` / `master` 或 `workflow_dispatch` | — |
| Build | `docker/build-push-action` 使用根目录 `Dockerfile` | 镜像 digest |
| Push | `docker/login-action` + GHCR | `IMAGE:sha` + `IMAGE:latest` |
| Deploy | `kubectl set image` + `rollout status` | 集群内新版本 Pod |

可选扩展：合并前 **CI** 跑 `ruff`/`pytest`；**CD** 使用 Argo CD GitOps 替代裸 kubectl。

---

## 四、任务 9：设计说明

### 1. 为什么必须容器化

镜像将 **运行时、依赖、配置** 固化，消除「在我机器能跑」差异；与 **K8s** 结合后可声明 **副本、资源、探针、滚动发布**，是生产交付与弹性伸缩的前提。

### 2. Kubernetes 如何实现高可用

- **多副本 Deployment + PodDisruptionBudget**：节点维护或故障时仍保留最小可用实例。  
- **Service 负载均衡**：流量分散到健康 Pod。  
- **HPA**：按 CPU/自定义指标自动扩容。  
- **有状态工作负载**：PostgreSQL/MinIO/Kafka 生产建议使用 **Operator / 云托管** 实现选主、备份与跨 AZ。

### 3. CI/CD 如何提升效率

流水线将 **构建、推送、部署** 自动化，缩短从合并到上线的时间，减少人为误操作；与 **镜像不可变标签（:git-sha）** 结合可快速回滚（`kubectl rollout undo`）。

---

## 五、高可用与降级（任务 5、6）

- **backend**：`replicas: 2` 起 + **HPA** + **PDB**；详见 `backend-deployment.yaml`、`backend-hpa.yaml`。  
- **PostgreSQL**：单副本 Deployment 仅为演示；生产请 **Patroni / 云 RDS**；本仓库提供 **CronJob 逻辑备份** 示例。  
- **MinIO**：单副本 + PVC；生产可选 **分布式 MinIO / 对象存储多 AZ**。  
- **降级**：环境变量 **`DEGRADED=true`** 关闭 `/graph` 等非核心路径；读路径可走 **Redis 读穿缓存**（业务层已实现部分缓存策略）。
