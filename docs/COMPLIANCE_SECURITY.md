# 合规与安全体系

## 一、数据脱敏（代码）

- 模块：`backend/core/masking.py`
- 规则：
  - **手机号**：11 位数字 → `138****1234`（`mask_phone`）
  - **银行卡**：保留后 4 位 → `****1234`（`mask_bank_card`）
  - **字典浅层脱敏**：`mask_dict_values(data, phone_keys=..., bank_keys=...)`

业务侧在序列化响应前对含手机/卡号字段调用上述函数；`/compliance/settings` 返回规则说明。

---

## 二、表设计

### 1. `audit_logs`（已存在）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | PK | |
| user_id | int, nullable | 操作人 |
| case_id | int, nullable | 关联案件 |
| action | varchar(64) | 如 `query_person_portrait`、`export_generate` |
| resource_type | varchar(64) | 资源类型 |
| resource_id | varchar(128) | 资源标识 |
| ip_address | varchar(64) | |
| user_agent | varchar(512) | |
| detail | json | 扩展 |
| created_at | timestamptz | |

索引：`user_id`、`case_id`、`action`、`created_at`、`resource_type+resource_id`。

### 2. `export_requests`（新增）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | PK | |
| applicant_id | FK → users.id | 申请人 |
| case_id | FK → cases.id | 案件 |
| person_id | varchar(256) | 报告对象 |
| file_format | varchar(16) | `pdf` / `docx` |
| status | varchar(32) | `pending` / `approved` / `rejected` |
| reviewer_id | FK → users.id, nullable | 审批人 |
| review_note | text, nullable | |
| reviewed_at | timestamptz, nullable | |
| created_at / updated_at | timestamptz | |

---

## 三、导出审批流程

1. `POST /compliance/export-requests` 提交申请（`case_id + person_id + file_format`）。
2. 管理员 `POST /compliance/export-requests/{id}/approve` 或 `.../reject`。
3. 审批通过后，调用 `POST /reports/generate` 时在 body 中携带 **`export_request_id`**（与 `case_id`/`person_id`/`format` 一致）。

若 `COMPLIANCE_EXPORT_APPROVAL_REQUIRED=true`（默认），**非 admin** 必须提供已审批的 `export_request_id`。**admin** 可跳过该约束。

环境变量：`COMPLIANCE_EXPORT_APPROVAL_REQUIRED`（`backend/core/config.py`）。

---

## 四、审计日志

- 写入：`backend/service/audit_service.py` + `backend/repository/audit_repo.py`
- 已挂接：
  - 线索列表 / 人物画像 / 线索详情（查询行为）
  - 导出申请创建、审批、驳回
  - 报告生成任务投递（导出行为）
- 查询：`GET /compliance/audit-logs`（管理员可查全量；普通用户仅本人 `user_id`）

---

## 五、权限控制

- **案件**：`GET /case?scope=all` 仅 **admin** 列出全部案件；普通用户仅本人案件。
- **案件详情/改/删**：**admin** 可访问任意案件；普通用户仅 `user_id` 匹配自己的案件。
- **导出审批**：仅 **admin**。
- **审计日志**：**admin** 可查全局；普通用户仅本人记录。

---

## 六、API 一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/compliance/settings` | 脱敏说明与导出策略开关 |
| POST | `/compliance/export-requests` | 申请导出 |
| GET | `/compliance/export-requests?scope=mine\|all` | 我的申请 / 管理员全部 |
| POST | `/compliance/export-requests/{id}/approve` | 审批通过 |
| POST | `/compliance/export-requests/{id}/reject` | 驳回 |
| GET | `/compliance/audit-logs` | 审计日志 |
| POST | `/reports/generate` | body 增加可选 `export_request_id`（合规开启时普通用户必填） |

（经前端 `/api` 代理后路径前缀为 `/api`）
