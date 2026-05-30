# 前端工程级架构（Vue 3）

本文描述目录约定、状态、API、类型与全局机制，**不包含业务实现与 UI**。实现落点见 `frontend/src/` 对应文件。

---

## 一、目录结构

```
frontend/src/
├── api/
│   ├── client.ts          # Axios 单例（鉴权、解包、错误、全局 loading、request_id）
│   ├── envelope.ts        # ApiEnvelope 与 request_id 提取
│   ├── request.ts         # 兼容 re-export（旧 import 路径）
│   └── modules/           # 按领域聚合 API（与后端模块对齐，逐步充实）
├── components/           # 通用/复合展示组件（无路由）
├── composables/          # usePermission、useGlobalLoading、useTaskPoller …
├── constants/
├── layouts/
├── modules/               # 业务模块门面（graph / clue / analysis / case）
│   ├── case/
│   ├── graph/
│   ├── clue/
│   └── analysis/
├── pages/                 # 现有页面（迁移中，目标为 views/）
├── views/                 # README：页面级组件目标目录
├── router/
├── state/
│   └── httpContext.ts     # 全局请求计数 + lastRequestId（不依赖 Pinia 初始化顺序）
├── store/
│   ├── modules/           # case / graph / clue / task 四 store
│   ├── case.ts            # 兼容导出 useCaseStore
│   ├── user.ts
│   └── …
├── types/
│   ├── domain.ts          # Case、Clue、Graph*、AnalysisTask
│   └── axios.d.ts         # AxiosRequestConfig 扩展
├── utils/
└── main.ts
```

**为何这样拆**：`api/client` 与 `state/httpContext` 解耦拦截器与 Pinia 生命周期；`modules/*` 提供稳定业务入口，避免页面直接深链 store/types；`views` 与 `pages` 双轨仅过渡期存在。

---

## 二、Pinia 状态设计

| Store | 文件 | 职责 |
|-------|------|------|
| **caseStore** | `store/modules/case.store.ts` | 案件列表、当前 `currentCaseId`、会话内分析/风险缓存、列表 loading |
| **graphStore** | `store/modules/graph.store.ts` | 当前案件绑定、布局模式、选中节点/边、子图 payload 缓存、视窗元数据 |
| **clueStore** | `store/modules/clue.store.ts` | 按 case 缓存线索列表、选中线索 id |
| **taskStore** | `store/modules/task.store.ts` | 按 case 缓存任务列表、轮询 id 集合 |

统一从 `store/modules/index.ts` 或 `modules/*/index.ts` 引用。**切换案件时**建议调用 `graphStore.resetForCaseSwitch()`、`clueStore`/`taskStore` 的 `bindCase`/`clearForCase`（由路由守卫或页面 orchestrate，不在 store 内写死路由依赖）。

---

## 三、API 封装规范

- **单例**：`import http from '@/api/client'`（或 `api/request` 兼容路径）。
- **响应**：成功时拦截器返回 `data`；错误统一 `notifyError`/`notifyWarning`（可 `silentError: true` 关闭）。
- **全局 loading**：默认每个请求 `loadingCount++/--`；轮询传 `skipGlobalLoading: true`。
- **request_id**：从 envelope 写入 `globalHttpContext.lastRequestId`，便于排错与日志关联。

类型扩展见 `types/axios.d.ts`：`silentError`、`skipGlobalLoading`。

---

## 四、类型系统

核心领域类型：`types/domain.ts`（`types/index.ts` 再导出）。

- `Case`、`Clue`、`GraphNode`、`GraphEdge`、`AnalysisTask`  
- API 层局部 DTO（如 `CaseOut`）可继续放在 `api/case.ts`，与后端演进对齐后再与 `Case` 合并或映射。

---

## 五、全局机制

| 能力 | 实现要点 |
|------|----------|
| **全局 loading** | `state/httpContext` + `composables/useGlobalLoading.ts`；可在根布局用 `v-loading` 绑定 `isLoading` |
| **全局错误提示** | 仍在 `api/client` 拦截器调用 `notifyError`；页面级可 `silentError` |
| **权限（基础）** | `composables/usePermission.ts` + 路由 `meta.roles` + `router/guard.ts`（守卫逻辑可继续增强） |

---

## 六、与后端契约

- 响应信封：`code` / `msg` / `data` / `request_id`（见 `api/envelope.ts`）。
- 案件维度：后续接口以 `case_id` 为路径或 body 显式传递（见 `BACKEND_FOUNDATION.md`）。

---

*变更时请同步更新本文与 `SYSTEM_ARCHITECTURE.md` 及 `docs/README.md`。*
