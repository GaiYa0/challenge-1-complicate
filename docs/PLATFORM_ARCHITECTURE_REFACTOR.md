# 中大型数据分析平台：工程架构审视与演进设计

> 角色：**Tech Lead / 资深全栈架构师**  
> 目标：在**不推翻重写**的前提下，说明当前模块划分、指出具体问题、给出**可演进的目录结构**与**核心模块边界**，为图谱、画像、规则引擎等复杂能力打底。  
> 本文**不实现业务逻辑**，仅做架构层约束与拆分建议。

---

## 1. 当前仓库模块划分（事实描述）

### 1.1 运行时主体：后端单体 `backend/`

| 目录 | 职责（现状） |
|------|----------------|
| `api/` | FastAPI 路由：HTTP 入参、依赖注入、转调 service；部分路由承载偏「应用层」逻辑（需收敛）。 |
| `service/` | 业务编排：文件、存储、分析投递、特征、模型、图、任务、健康度等。 |
| `repository/` | SQLAlchemy 数据访问（user、file、case、feature、feedback、model_registry 等）。 |
| `model/` | ORM 模型拆分文件 + `models.py` 桶导出。 |
| `schema/` | Pydantic 请求/响应与 API 契约。 |
| `core/` | 配置、DB、JWT、响应信封、异常、租户/权限、安全审计、事务。 |
| `middleware/` | JWT 门、限流等横切。 |
| `tasks/` | Celery：分析、清洗、特征、模型、成本、补偿等；`runtime.py` 供 worker 拉取 DB/Redis/MinIO。 |
| `events/` | Kafka 生产/消费、DLQ、事件 schema。 |
| `infra/` | MinIO、Redis、分层缓存、数据湖辅助。 |
| `data_platform/` | 统一访问、批/流占位（与真实分析管线衔接不足，属扩展点）。 |
| `utils/` | 零散工具（分析、文件）。 |

**入口**：根目录 `main.py` → `backend.main:app`（符合单入口约定）。

### 1.2 前端 `frontend/src/`

| 目录 | 职责（现状） |
|------|----------------|
| `api/` | Axios 封装，按资源拆分（file、case、analyze、task、graph…）。 |
| `pages/` | 页面级路由组件（案件流、管理端）。 |
| `components/` | 图表（ECharts）、调查业务组件、G6 `GraphView`。 |
| `store/` | Pinia：user、case、ui、data 等；**案件维度的分析/风险结果部分仅存内存**。 |
| `composables/` | 任务轮询等可复用逻辑。 |
| `router/` | 路由与守卫。 |

### 1.3 并行演进：`services/`

- `gateway/`、`user_service/`、`file_service/` 等与 **当前 Docker Compose 主路径**并行存在，用于**微服务化预演**；与 `backend/` 单体在概念上重复（用户、文件），易造成「双栈心智」。

### 1.4 运维与交付

- `deploy/k8s/`：编排清单。  
- `docker-compose*.yml`：本地/分段运行时。  
- `.github/workflows/`：CI/CD。  
- `docs/`：系统架构、微服务设计、Celery、成本等**文档与代码脱节风险**需持续对齐。

---

## 2. 不合理之处（具体、可验证）

### 2.1 领域边界：`case`（案件）未贯穿数据平面

- **ORM**：`Case` 存在于 PG，但 `File` 模型仅有 `user_id` + `dataset` 字符串，**无 `case_id` 外键**（见 `backend/model/file.py`）。  
- **后果**：「案件」仅为 UI 路由上下文；上传用 `dataset=case-{id}` 约定，**列表/分析接口仍按租户文件全局拉取**，无法在数据层做强一致隔离与审计。  
- **与目标冲突**：要求「所有数据必须有 case_id 归属」时，必须先补**数据模型与 API 契约**，否则后续图谱/画像/规则无法按案件做授权与生命周期。

### 2.2 路由与分层：`health` 模块职责混杂

- `/analysis/graph` 等**分析向**能力挂在 `health` 相关模块（见 `backend/api/health.py`），而「健康检查/运维面板」与「业务图可视化」生命周期、缓存策略、权限模型不同。  
- **后果**：新人从路由名无法推断边界；扩展开来会出现更多「顺手塞在 health」的接口，**运维面与业务面耦合**。

### 2.3 图能力双轨：权限与数据模型不一致

- `graph` 路由下部分接口 **require admin**（建点建边），而调查页消费的是 **另一路径**拉取的子图。  
- Neo4j 中模型以演示为主（如 `User` + `TRANSFER`），**与 PG 案件/人物主键无统一 ID 策略**。  
- **后果**：图谱服务化时会出现「管理员种子图」与「业务图」两套语义，难以做**可重复的 case 级子图投影**。

### 2.4 异步任务：`case_id` 未成为一等公民

- `analyze_data_task` 等任务以 `(kind, filename, user_id)` 为主键语义（见 `backend/tasks/analyze_task.py`），**缺少 case_id**。  
- **后果**：同一文件在不同案件复用时无法区分结果；缓存 key（Redis）也无法按案件隔离；**不符合「所有分析异步且可归属」的中台要求**。

### 2.5 `service/` 层粒度不均

- 存在「薄封装 + 重任务」组合：`analyze_service` 仅投递 Celery，而实质算法在 `tasks/` + `data_pipeline_service`。  
- `data_platform/` 与 `tasks/` 职责边界模糊：批处理占位与 Celery 管道谁拥有「标准 DataFrame」定义不清晰。  
- **后果**：新增「规则引擎」「画像引擎」时容易在 task 内堆代码，**难以单测与复用**。

### 2.6 事件与领域：`events/` 与业务状态未闭环

- Kafka 事件已定义 topic 与 handler，但**案件状态、任务结果落库**与事件顺序、幂等等**无统一 Outbox/状态机**（中大型系统必备）。  
- **后果**：扩消费者、重放、对账困难。

### 2.7 前端：API 驱动不足、状态分裂

- `store/case.ts` 对分析/风险结果做**会话内缓存**，与后端任务结果**无单一事实来源**（刷新即丢）。  
- 页面直接 `listDbFiles()` **不带 case_id**，与架构目标冲突。  
- **后果**：无法支撑多用户协作与同案多终端一致视图。

### 2.8 `services/` 与 `backend/` 重复

- 用户、文件等领域在两边各有一套，**无强制规范**说明「新功能写单体还是写微服务」。  
- **后果**：长期维护成本上升；建议明确 **单体为唯一运行时真相**，`services/` 仅作拆分实验或生成契约样本。

---

## 3. 重构后的目录结构设计（演进式，非推翻）

原则：**保留现有包名与入口**，通过**新增包与渐进迁移**收口边界；大文件夹用注释标明「只允许依赖谁」。

### 3.1 后端 `backend/`（目标形态）

```
backend/
├── main.py                    # 不变：组装 app、注册路由
├── api/                       # 仅 HTTP 适配层（薄）
│   ├── v1/                    # 【新增】版本化对外 API（可选，推荐）
│   │   ├── cases/
│   │   ├── files/
│   │   ├── analysis/
│   │   ├── graph/
│   │   └── ...
│   └── ...                    # 过渡期可保留原路由，内部转发到 v1 service
├── core/                      # 横切：config、db、security、response（保持）
├── contracts/                 # 【新增】跨模块 DTO、枚举、错误码（仅类型，无 IO）
├── domain/                    # 【新增】领域层（可选子包，按 bounded context 拆）
│   ├── case/                  # 案件聚合：实体、领域服务接口、工厂
│   ├── artifact/              # 文件/导入产物：与 MinIO 键策略、case 绑定
│   ├── analysis/              # 分析作业：Job 定义、状态、与 Celery 映射
│   ├── graph_projection/      # 图投影：PG 事实 → Neo4j 子图策略（接口）
│   └── profile_rule/          # 画像与规则：占位接口，禁止写具体规则实现
├── application/               # 【新增】应用服务（用例）：编排 domain + infra
│   ├── ports/                 # 端口：抽象仓储、消息、图客户端（Protocol）
│   └── use_cases/             # 用例：CreateCase、UploadArtifact、EnqueueAnalysis…
├── infrastructure/            # 【新增】适配器实现（可渐进从 service/ 迁入）
│   ├── persistence/           # repository 实现
│   ├── messaging/             # kafka、celery 封装
│   ├── graph/                 # neo4j driver 封装
│   └── object_storage/        # minio
├── service/                   # 【过渡期】逐步变薄，最终或合并入 application/
├── repository/                # 过渡期保留；长期迁入 infrastructure/persistence
├── model/                     # ORM 保持；新增 migration 策略需单独规划（当前 create_all）
├── schema/                    # API 层 schema；与 contracts/ 对齐字段
├── tasks/                     # Celery：仅保留「任务入口 + 调用 application 用例」
├── events/                    # 事件：与 outbox 策略对齐
├── middleware/
├── infra/                     # 过渡期保留；长期迁入 infrastructure/
└── data_platform/             # 批/流：仅作为「数据平台」边界，消费 application 端口
```

**说明**：若团队规模暂小，可只先建 **空包** `contracts/`、`application/ports/`，把「禁止事项」写进代码规范（如 tasks 不得直接 `pd.read_csv` 超过三行而不经 pipeline 端口）。

### 3.2 前端 `frontend/src/`（目标形态）

```
src/
├── api/
│   ├── client.ts              # 【从 request.ts 抽】axios 实例 + 拦截器
│   ├── envelope.ts            # 【新增】统一解包、错误类型
│   └── modules/               # 【新增】按领域拆分：case、artifact、analysisJob、graph…
├── domain/                    # 【新增】纯 TS 类型与常量（与后端 contracts 对齐）
├── composables/
├── features/                  # 【新增】按功能聚合（可选）
│   ├── investigation/         # 调查流程：导入、分析、报告
│   └── admin/
├── pages/                     # 薄页面：组装 features
├── components/
├── store/
│   └── modules/               # 【新增】按领域；**服务端状态**以 query 或 refetch 为主
└── router/
```

**原则**：页面不直接拼 URL 字符串；**caseId 从路由注入 composable**，所有 API 调用经 **modules** 层带 `caseId` 参数。

### 3.3 `services/`（微服务预演）

- **建议**：在文档中标记为 **「契约与示例」**，新功能默认不进 `services/`，除非明确做 **边界服务拆分**（并配套独立 DB 与 CI 镜像）。

---

## 4. 核心模块边界定义

### 4.1 Case（案件）— 聚合根

- **拥有**：`case_id`、租户内可见性、生命周期状态。  
- **不直接做**：文件字节读写、图计算；**只引用** ArtifactId / JobId。  
- **对外接口**：创建、归档、列表、权限校验（与 `user_id` 绑定）。

### 4.2 Artifact（文件/导入产物）— 实体

- **必须字段**：`case_id`、`owner_user_id`、存储键（MinIO）、逻辑名、MIME/类型、版本。  
- **服务**：上传登记、预签名、按 case 列表、删除（级联策略需定义）。  
- **禁止**：在 API 层直接操作 MinIO 而不写元数据。

### 4.3 AnalysisJob（分析作业）— 实体 + 状态机

- **必须字段**：`job_id`、`case_id`、`artifact_id` 或 `job_input_ref`、`kind`（pipeline 类型）、`status`（queued/running/succeeded/failed）、`result_ref`（PG JSON 或对象键）。  
- **异步**：Celery **仅**负责执行与重试；**状态机与幂等**在 `application` 层定义。  
- **缓存**：Redis key **必须含 case_id**（与 user_id 组合）。

### 4.4 GraphProjection（图投影）— 领域服务

- **输入**：案件范围内的事实（转账、关系边）。  
- **输出**：Neo4j 中 **命名空间化**子图（如 `tenant_id` + `case_id` 前缀或独立 database，需后续选型）。  
- **禁止**：在 FastAPI 路由里写 Cypher；统一经 `graph` 端口/adapter。

### 4.5 RulesEngine / Profile（规则与画像）— 未来子域

- **边界**：仅定义 **端口**（输入特征快照、输出结构化结果、版本号）；**不**在架构文档中实现 DSL。  
- **执行位置**：Celery worker 内调用 domain 策略，**结果落 PG** 并可选发 Kafka。

### 4.6 Events & Integration（集成）

- **Kafka**：仅承载「已提交事实」的**异步通知**；**权威状态**仍在 PG。  
- **建议演进**：引入 **Transactional Outbox**（同库表 + 定时投递），避免「业务已提交但事件未发」。

### 4.7 API 层（`api/`）

- **只做**：参数校验、鉴权、调用 application 用例、返回 envelope。  
- **禁止**：嵌入 SQL、Cypher、长段 Pandas。

### 4.8 前端

- **单一数据源**：列表/详情以 **服务端 API** 为准；Pinia 仅缓存 **UI 状态**（选中项、折叠），不替代持久化结果。  
- **caseId**：所有调查相关请求 **显式传参**（路径或 query），禁止依赖隐式全局。

---

## 5. 与现有文档的关系

- `docs/SYSTEM_ARCHITECTURE.md`：数据湖与流批愿景；**本文档**约束 **单体内部**如何收口以承接该愿景。  
- `docs/MICROSERVICES_DESIGN.md`：与 `services/` 对齐；**运行时默认以 `backend/` 为准**，避免双实现。

---

## 6. 可验证的演进里程碑（非业务实现）

| 里程碑 | 验证方式 |
|--------|----------------|
| M1：`File` 或并行表出现 `case_id` 非空约束 | 迁移后 PG 约束 + 上传 API 单测 |
| M2：分析任务 payload 含 `case_id` | Celery 任务签名 + Redis key 快照 |
| M3：`/analysis/*` 从 `health` 迁出 | OpenAPI 路由分组 + 集成测试路径 |
| M4：前端 `listFiles` 仅传 `caseId` | E2E 或接口契约测试 |

---

*文档维护：架构变更时同步更新本节与 `docs/SYSTEM_ARCHITECTURE.md` 交叉引用。*
