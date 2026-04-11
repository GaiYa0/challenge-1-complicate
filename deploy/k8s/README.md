# Kubernetes 生产部署清单

## 首次部署顺序

1. 创建命名空间（已含于 `kustomization.yaml`）  
2. 创建 Secret（**不要提交真实文件**）：
   - 复制 `postgres-secret.example.yaml` → `postgres-secret.yaml` 并 `kubectl apply -f postgres-secret.yaml`
   - 复制 `minio-secret.example.yaml` → `minio-secret.yaml`
   - 复制 `backend-secret.example.yaml` → `backend-secret.yaml`
3. 应用清单：

```bash
kubectl apply -k deploy/k8s/
```

4. 安装 Ingress Controller（若未安装），例如：

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller/main/deploy/static/provider/cloud/deploy.yaml
```

5. 将 `ingress.yaml` 中 `host` 改为你的域名，并配置 DNS 指向 Ingress 入口 IP。

## 与 CI/CD 联动

GitHub Actions：`.github/workflows/k8s-ci-cd.yml`  
在仓库 **Settings → Secrets** 添加 `KUBE_CONFIG`：`~/.kube/config` 全文 **base64** 编码后的字符串。

## 监控

- Prometheus：抓取带 `prometheus.io/scrape: "true"` 注解的 Pod（backend 已配置）。  
- Grafana：默认 `admin` / 请在 `grafana-deployment.yaml` 修改 `GF_SECURITY_ADMIN_PASSWORD`，建议另加 Ingress 与认证。

## 降级

Deployment 中可为 backend 增加环境变量 `DEGRADED=true`（或通过 ConfigMap），将关闭图谱等非核心路由；缓存命中由应用层 Redis 读穿策略承担（见业务代码）。
