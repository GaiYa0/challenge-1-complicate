# 启动脚本（run）

Docker Compose 与前端本地/生产构建的快捷入口，详细说明见仓库根目录 [README.md](../README.md)。

```bash
chmod +x run/*.sh   # 首次可选
./run/run.sh help
```

一键前后端（Docker）：`./run/docker-up.sh` 完成后打开 **<http://127.0.0.1:8080>**（API 文档仍在 **:8000/docs**）。

## 前后端分开 Compose

| 步骤 | 命令（均在仓库根目录） |
|------|------------------------|
| 只起后端栈（依赖 + API + Worker + Consumer） | `docker compose -f docker-compose.backend.yml --env-file .env.dev up -d --build` |
| 再起前端（Nginx 8080） | `docker compose -f docker-compose.backend.yml -f docker-compose.frontend.yml --env-file .env.dev up -d --build web` |
| 仍一键全栈 | `docker compose --env-file .env.dev up -d --build`（根目录 `docker-compose.yml` 已 `include` 两个文件） |

说明：`docker-compose.frontend.yml` 不含独立网络定义，**不要**单独 `-f docker-compose.frontend.yml up`；须带上 `docker-compose.backend.yml`，以便与已有 `challenge-backend` 共用 `app-net`。
