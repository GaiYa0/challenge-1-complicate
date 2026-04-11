# user-service（完整最小示例）

## 结构

`api/` · `service/` · `repository/` · `model/` · `schema/` · `core/` · `main.py`

## 配置

| 变量 | 说明 |
|------|------|
| `DATABASE_URL` | 仅 **user_db** |
| `JWT_SECRET` / `JWT_EXPIRE_MINUTES` | JWT |
| `INTERNAL_API_TOKEN` | 其他微服务调用 `/internal/v1/*` 时请求头 `X-Internal-Token` |

## 运行

在项目根目录：

```bash
pip install -r services/user_service/requirements.txt
export DATABASE_URL=postgresql://user:password@localhost:5432/user_db
PYTHONPATH=. uvicorn services.user_service.main:app --port 8001
```

## 接口示例

- `POST /auth/login` — `{"username":"...","password":"..."}` → `access_token`
- `GET /internal/v1/users/{id}` — 需 `X-Internal-Token`
- `POST /internal/v1/token/validate` — body `{"token":"..."}`

服务间 HTTP 客户端示例见 `services/file_service/clients/user_service_client.py`。

## 经网关的链路演示

1. 登录（网关 `8000`）：`POST http://localhost:8000/user/auth/login`
2. 携带 `Authorization: Bearer <token>` 调用：`GET http://localhost:8000/user/v1/chain/file-health`（可带 `X-Request-ID`）
3. 网关校验 JWT 后转发到本服务的 `/v1/chain/file-health`，本服务再 HTTP 调用 file-service `/health`。
