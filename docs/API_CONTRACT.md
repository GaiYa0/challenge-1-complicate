# 前后端接口契约（API Contract）

> **目的**：前端可据此独立 Mock/联调，无需猜测字段。  
> **约定**：除登录等公开接口外，均需 **Authorization: Bearer &lt;access_token&gt;**；可选 **X-Tenant-ID**（与现有实现一致）。  
> **路径说明**：下表「后端路径」指 FastAPI 挂载路径。前端若 `baseURL='/api'` 且 Nginx/Vite 将 `/api` 剥掉转发，则 **浏览器侧完整 URL** = `baseURL + 后端路径`（例如 `/api/case` → 后端 `/case`）。

---

## 统一响应信封（所有业务接口）

HTTP 200 时响应体（JSON）：

```json
{
  "code": 0,
  "msg": "success",
  "data": {},
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| code | int | **0** 成功；**非 0** 失败（见「错误码」） |
| msg | string | 人类可读说明 |
| data | object \| array \| null | 业务数据；失败时可为 null 或附带 detail |
| request_id | string | 与响应头 **X-Request-ID** 一致，用于链路排查 |

**失败时**：可能仍为 HTTP 200（`ServiceError`）或 4xx/5xx，**body 仍优先读 `code` + `msg`**。

---

## 一、核心 REST 接口

### 1. 案件（Case）

| 状态 | 方法 | 后端路径 | 说明 |
|------|------|----------|------|
| 已实现 | GET | `/case` | 当前用户案件列表 |
| 已实现 | POST | `/case` | 创建案件 |
| 已实现 | GET | `/case/{case_id}` | 获取单个案件 |
| 已实现 | PUT | `/case/{case_id}` | 更新案件 |
| 已实现 | DELETE | `/case/{case_id}` | 删除案件 |
| **规划** | GET | `/case/{case_id}/context` | **当前案件上下文**（聚合摘要，见下） |

#### 1.1 创建案件 `POST /case`

**请求体**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 案件名称，1～256 字符 |
| case_number | string | 否 | 编号 |
| note | string | 否 | 备注 |

**响应 `data`（CaseOut）**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| name | string | |
| case_number | string \| null | |
| note | string \| null | |
| status | string | 如 `active` / `completed` |
| extra_metadata | object \| null | 扩展 JSON |
| created_at | string | ISO8601 |
| updated_at | string | ISO8601 |

**示例**

```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "id": 12,
    "name": "某某渎职案",
    "case_number": "2026-001",
    "note": null,
    "status": "active",
    "extra_metadata": null,
    "created_at": "2026-04-16T10:00:00",
    "updated_at": "2026-04-16T10:00:00"
  },
  "request_id": "..."
}
```

#### 1.2 获取案件 `GET /case/{case_id}`

**路径参数**：`case_id` int

**响应 `data`**：同 CaseOut。

#### 1.3 当前案件上下文（规划）`GET /case/{case_id}/context`

> **用途**：一次返回前端布局所需摘要（案件信息 + 文件数量 + 最近任务状态占位），**非**全量列表。

**响应 `data`（建议结构）**

| 字段 | 类型 | 说明 |
|------|------|------|
| case | CaseOut | 案件基本信息 |
| file_count | int | 本案绑定文件数 |
| last_analysis | object \| null | 最近一次分析任务摘要（public_id、status） |
| hints | string[] | 可选引导文案 |

**示例**

```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "case": { "id": 12, "name": "某某案", "case_number": "2026-001", "note": null, "status": "active", "extra_metadata": null, "created_at": "...", "updated_at": "..." },
    "file_count": 3,
    "last_analysis": { "public_id": "uuid", "status": "succeeded" },
    "hints": []
  },
  "request_id": "..."
}
```

---

### 2. 文件（File）

| 状态 | 方法 | 后端路径 | 说明 |
|------|------|----------|------|
| 已实现 | POST | `/upload` | 上传文件 |
| 已实现 | GET | `/db/files` | 当前用户**全部**文件详情列表（**未按 case 过滤**） |
| **规划** | GET | `/case/{case_id}/files` | **仅本案**绑定文件列表 |
| **规划** | POST | `/case/{case_id}/files` | 上传并绑定本案（或 multipart + case_id） |

#### 2.1 上传（现状）`POST /upload`

**Query**

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| dataset | string | 否 | default | 建议传 `case-{case_id}` 作约定，直至绑定表接口上线 |
| version | string | 否 | v1 | |

**Body**：`multipart/form-data`，字段名 `file`

**响应 `data`（FileUploadData）**

| 字段 | 类型 | 说明 |
|------|------|------|
| filename | string | 逻辑文件名 |
| presigned_url | string | 预签名 URL |
| bucket_name | string | |
| object_name | string | |
| version | string | |
| dataset | string | |
| data_layer | string | 如 `raw` |

#### 2.2 获取案件文件列表（规划）`GET /case/{case_id}/files`

**Query（分页，见第三节）**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 默认 1 |
| page_size | int | 否 | 默认 20，最大 100 |

**响应 `data`**

```json
{
  "items": [
    {
      "id": 1,
      "filename": "bank.csv",
      "role": "bank_statement",
      "dataset": "case-12",
      "upload_time": "2026-04-16T10:00:00",
      "presigned_url": "https://..."
    }
  ],
  "total": 3,
  "page": 1,
  "page_size": 20
}
```

| 字段 | 说明 |
|------|------|
| items[].id | files 表主键 |
| items[].role | case_files.role |
| total | 总条数 |

---

### 3. 线索（Clue）

| 状态 | 方法 | 后端路径 | 说明 |
|------|------|----------|------|
| **规划** | GET | `/case/{case_id}/persons/{subject_key}/clues` | 某人物线索列表 |
| **规划** | GET | `/clues/{clue_id}` | 线索详情 |

**说明**：`subject_key` 与图谱/业务人物主键一致（URL 编码）。

#### 3.1 获取人物线索列表（规划）

**Query**

| 参数 | 类型 | 说明 |
|------|------|------|
| page | int | 默认 1 |
| page_size | int | 默认 20 |
| risk_level | string | 可选：`high` / `medium` / `low` |

**响应 `data`**

```json
{
  "items": [
    {
      "id": 101,
      "case_id": 12,
      "subject_key": "zhang_san",
      "title": "异常大额转出",
      "summary": "近30日…",
      "status": "open",
      "risk_level": "high",
      "risk_score": 82.5,
      "category": "fund",
      "analysis_task_id": 55,
      "created_at": "2026-04-16T10:00:00",
      "updated_at": "2026-04-16T10:00:00"
    }
  ],
  "total": 5,
  "page": 1,
  "page_size": 20
}
```

#### 3.2 获取线索详情（规划）`GET /clues/{clue_id}`

**响应 `data`**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | |
| case_id | int | |
| subject_key | string | |
| title | string | |
| summary | string \| null | |
| status | string | open / confirmed / dismissed |
| risk_level | string | |
| risk_score | number \| null | |
| category | string \| null | |
| analysis_task_id | int \| null | |
| rule_hits | array \| object \| null | 规则命中 |
| feature_snapshot | object \| null | 特征摘要 |
| risk_prompts | array \| null | 风险提示 |
| extra_metadata | object \| null | |
| created_at | string | |
| updated_at | string | |

**示例**

```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "id": 101,
    "case_id": 12,
    "subject_key": "zhang_san",
    "title": "异常大额转出",
    "summary": "…",
    "status": "open",
    "risk_level": "high",
    "risk_score": 82.5,
    "category": "fund",
    "analysis_task_id": 55,
    "rule_hits": [{ "code": "LARGE_TRANSFER", "label": "单笔超阈值" }],
    "feature_snapshot": { "transfer_out_30d": 186.4 },
    "risk_prompts": [{ "level": "high", "text": "…" }],
    "extra_metadata": null,
    "created_at": "2026-04-16T10:00:00",
    "updated_at": "2026-04-16T10:00:00"
  },
  "request_id": "..."
}
```

---

### 4. 图谱（Graph）

| 状态 | 方法 | 后端路径 | 说明 |
|------|------|----------|------|
| 已实现 | GET | `/analysis/graph` | **关系网络**子图（Neo4j），需登录 |
| 已实现 | GET | `/graph/degree` | 出度统计（**admin**） |
| 已实现 | GET | `/graph/relations` | 转账边列表（**admin**） |

#### 4.1 获取关系网络（现状）`GET /analysis/graph`

**Query**

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| edge_limit | int | 否 | 500 | 1～5000 |

**响应 `data`（GraphVisualizationData）**

| 字段 | 类型 | 说明 |
|------|------|------|
| nodes | array | `{ "id": string, "label": string }` |
| edges | array | `{ "id": string, "source": string, "target": string }` |

**示例**

```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "nodes": [
      { "id": "u1", "label": "张某" },
      { "id": "u2", "label": "李某" }
    ],
    "edges": [
      { "id": "e1", "source": "u1", "target": "u2" }
    ]
  },
  "request_id": "..."
}
```

#### 4.2 获取关系网络（规划，按案件）

**建议路径**：`GET /case/{case_id}/graph`  
**Query**：`edge_limit` 同上；服务端仅返回 **本案投影** 子图（与 `case_id` 数据一致）。

---

### 5. 分析任务（Analysis Task）

| 状态 | 方法 | 后端路径 | 说明 |
|------|------|----------|------|
| 已实现 | GET | `/task/{task_id}` | Celery **task_id** 状态 |
| 已实现 | GET | `/task/result/{task_id}` | 任务结果 |
| 已实现 | POST | `/analyze/*` 等 | 按 **filename** 投递（**无 case_id**） |
| **规划** | POST | `/case/{case_id}/analysis-tasks` | **创建**领域分析任务（含 case） |
| **规划** | GET | `/case/{case_id}/analysis-tasks/{public_id}` | 按 **public_id** 查状态 |

#### 5.1 查询任务状态（现状）`GET /task/{task_id}`

**路径参数**：`task_id` — Celery 返回的 UUID 字符串

**响应 `data`（TaskStatusData）**

| 字段 | 类型 | 说明 |
|------|------|------|
| state | string | PENDING / STARTED / SUCCESS / FAILURE / … |

**示例**

```json
{
  "code": 0,
  "msg": "success",
  "data": { "state": "SUCCESS" },
  "request_id": "..."
}
```

#### 5.2 创建分析任务（规划）`POST /case/{case_id}/analysis-tasks`

**请求体**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_type | string | 是 | 如 `clean` / `feature_extract` / `graph_build` / `clue_generate` / `pipeline_composite` |
| input_payload | object | 是 | 如 `{ "file_ids": [1,2], "options": {} }` |

**响应 `data`**

```json
{
  "task_id": "celery-uuid",
  "public_id": "analysis-task-uuid",
  "status": "queued"
}
```

| 字段 | 说明 |
|------|------|
| task_id | Celery 任务 id（与现轮询兼容） |
| public_id | analysis_tasks 表对外 id |
| status | queued |

#### 5.3 查询领域任务（规划）`GET /case/{case_id}/analysis-tasks/{public_id}`

**响应 `data`（建议）**

| 字段 | 类型 |
|------|------|
| public_id | string |
| case_id | int |
| task_type | string |
| status | string |
| celery_task_id | string \| null |
| input_payload | object |
| result_ref | object \| null |
| error_message | string \| null |
| started_at | string \| null |
| finished_at | string \| null |
| created_at | string |

---

## 二、分页规范

### 偏移分页（列表类默认）

| Query 参数 | 类型 | 默认 | 约束 |
|------------|------|------|------|
| page | int | 1 | ≥ 1 |
| page_size | int | 20 | 1～100（最大可由服务端配置） |

**响应**列表统一带：

```json
{
  "items": [],
  "total": 100,
  "page": 1,
  "page_size": 20
}
```

### 游标分页（可选，大数据量）

| Query | 说明 |
|-------|------|
| cursor | opaque 字符串，首次不传 |
| limit | 默认 20，最大 100 |

**响应**

```json
{
  "items": [],
  "next_cursor": "eyJpZCI6MTIzfQ==",
  "has_more": true
}
```

**约定**：新接口优先 **offset**；线索/审计等海量再启用 **cursor**。

---

## 三、错误码规范

与 `backend/core/error_codes.py` 及全局处理器对齐：

| code | 含义 | HTTP 常见 |
|------|------|-----------|
| 0 | 成功 | 200 |
| 40001 | 参数错误 | 422 |
| 40101 | 未认证 | 401 |
| 40301 | 无权限 | 403 |
| 40401 | 资源不存在 | 404 |
| 40901 | 冲突 | 409 |
| 42001 | 案件不存在 | 200/404 |
| 42002 | 案件无访问权 | 403 |
| 43001 | 文件不存在 | 200/404 |
| 44001 | 分析任务不存在 | 404 |
| 45001 | 线索不存在 | 404 |
| 50001 | 系统内部错误 | 500 |

**校验失败**（Pydantic）：`code: 42201`，`data` 内含 `errors` 数组。

**示例**

```json
{
  "code": 42001,
  "msg": "案件不存在",
  "data": null,
  "request_id": "..."
}
```

---

## 四、权限规则（基础）

| 规则 | 说明 |
|------|------|
| 认证 | 除 `/auth/login`、`/live`、`/ready`、`/metrics`、公开白名单外，均需有效 JWT |
| 案件 | `cases.user_id` 必须等于当前用户；**admin** 可扩展为全量（以服务端实现为准） |
| 文件 | 读取/删除仅能操作 **本人上传** 或与本案绑定且本人有权限的文件 |
| 图谱写 | `POST /graph/node`、`POST /graph/edge` 等为 **admin**（现状） |
| 图谱读 | `GET /analysis/graph` 为普通登录用户 |

**前端**：路由 `meta.roles`（如 `admin`）+ `usePermission()`；请求失败 **403** 时提示无权限。

---

## 五、与前端类型对照

| 契约对象 | TypeScript（`frontend/src/types/domain.ts`） |
|----------|---------------------------------------------|
| CaseOut / Case | `Case` |
| 线索 | `Clue` |
| GraphVisualizationData | `GraphNode` + `GraphEdge`（与 nodes/edges 数组一致） |
| 分析任务（规划） | `AnalysisTask` |

---

## 六、修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0 | 2026-04-16 | 初版：对齐现有路由 + 规划 case 绑定与线索/任务 |

后续后端实现规划接口时，应 **保持路径与字段名** 与本契约一致；变更需改版本号并通知前端。
