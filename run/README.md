# 启动脚本（run）

仅保留**前后端一体上线**脚本，统一走 Docker Compose。

```bash
chmod +x run/*.sh   # 首次可选
./run/run.sh help
```

## 可用脚本

- `./run/docker-up.sh`：构建并启动全栈（前端 Nginx + 后端 + 依赖）
- `./run/docker-down.sh`：停止全栈
- `./run/docker-logs.sh [service]`：查看日志（默认 `backend`）
- `./run/run.sh <subcommand>`：统一入口（`docker-up` / `docker-down` / `docker-logs`）

## 启动后访问地址

- 业务入口：<http://127.0.0.1:8080>
- API 文档：<http://127.0.0.1:8000/docs>
