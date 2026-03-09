# 城市街道视觉巡检 Agent 模块清单与框架选型

## 1. 目标

在已有总体设计基础上，把系统进一步细化成可实现的模块清单，并完成后端 Agent 编排框架选型，优先复用成熟框架，避免自研状态机、任务重试、长流程恢复、回传补偿等基础设施。

## 2. 先给结论

推荐采用如下技术组合：

- `FastAPI` 作为图片接入和管理接口层
- `Temporal` 作为 Agent 编排与长流程工作流内核
- `Pydantic v2` 作为配置与领域模型定义层
- `SQLAlchemy + PostgreSQL` 作为事件索引、审计与查询存储
- 对象存储（本地兼容 S3 亦可）作为原图、裁剪图、叠图、mask 的证据存储

其中，最关键的最终选型是：

- `Temporal` 作为主编排框架
- 不选择 `LangGraph`、`Celery`、`Prefect` 作为主工作流内核

原因是本项目的核心问题不是“多轮对话 Agent 推理”，而是“可靠、可回放、可审计、可恢复的双链路视觉巡检工作流编排”。

## 3. 为什么这个项目不应该先选通用 LLM Agent 框架

这个项目虽然被称为 Agent，但它的本质更接近：

- 一个强状态约束的视觉工作流系统
- 一个长生命周期事件处理系统
- 一个需要审计、重试、人工复核、双阶段回传、同事件更新的后端编排服务

它不属于以下类型：

- 通用聊天智能体
- 自由规划型多 Agent 协作系统
- 强依赖工具调用链推理的开放式任务代理

因此，主框架不应该优先围绕“LLM Agent loop”选型，而应该围绕：

- 工作流耐久性
- 步骤重试
- 状态持久化
- 事件更新
- 信号/人工介入
- 任务补偿

来选型。

## 4. 候选框架对比

### 4.1 Temporal

适合作为主编排框架。

优点：

- 核心能力就是 Durable Execution
- 支持把长流程写成代码化 Workflow
- 对失败步骤提供自动恢复、重试、定时器、信号机制
- 适合“同一事件跨同步和异步阶段持续推进”的模型
- 天然适合人工复核、回调重试、长时间等待外部输入等场景
- Python 生态可直接接入现有模型服务和后端栈

不足：

- 学习成本高于普通任务队列
- 需要额外部署 Temporal Server 或使用 Temporal Cloud
- 开发团队需要接受“Workflow + Activity”的编程模型

结论：

- 最适合本项目作为编排内核

### 4.2 LangGraph

更适合作为 LLM 驱动的 Agent 控制流框架，而不是本项目的主后端编排框架。

优点：

- 擅长表达带状态的 Agent 图结构
- 支持 human-in-the-loop
- 对模型调用链和 Agent 推理链比较友好

不足：

- 核心价值点仍偏向 LLM Agent 编排
- 对外部系统故障恢复、工作流长期持久化、后端补偿流程，并不是它的主卖点
- 需要你自己补更多后端可靠性约束

结论：

- 可作为将来某些复杂审证提示链的内部编排工具
- 不适合做整个巡检后端的主工作流内核

### 4.3 Celery

适合作为分布式任务队列，但不适合承担本项目的完整事件生命周期编排。

优点：

- 成熟、常见、容易找到工程经验
- 适合异步任务分发和批量处理

不足：

- 它本质是任务队列，不是 durable workflow 引擎
- 复杂状态流转、人工介入、同事件多阶段更新、补偿与可回放，最终仍会落回业务代码自研
- 很容易把系统写成“任务拼接 + 数据库状态表 + 大量补丁逻辑”

结论：

- 适合做模型批处理任务队列
- 不适合做你的主编排框架

### 4.4 Prefect

Prefect 更偏向 Python 工作流与数据流程编排，适合数据平台和调度型场景。

优点：

- Pythonic
- 支持动态工作流
- 可观测性和部署能力不错

不足：

- 更像 workflow orchestration/platform 工具
- 对你这个“后台服务内嵌事件生命周期引擎”的贴合度不如 Temporal
- 视觉巡检中的事件驱动、回调更新、人工复核、同事件长期演进，不是它最强的问题域

结论：

- 可以做数据流或离线流程
- 不作为本项目首选

## 5. 最终框架选型

### 5.1 主编排框架

最终选型：`Temporal`

原因：

1. 你这个系统最贵的不是模型调用，而是流程可靠性
2. 你已经明确需要同步初判和异步精检共享同一个 `event_id`
3. 你需要异步链路更新已有事件，而不是简单发一个新任务
4. 你需要对失败、回调、重试、等待、人工复核有明确状态控制
5. 如果不用 Temporal，这些能力最后都要自己在数据库状态机里重写一遍

Temporal 能把这些需求直接映射成：

- 一个 `InspectionEventWorkflow`
- 多个 `Activities`
- 对后台回传的重试策略
- 对人工复核或外部确认的信号机制
- 对长时间等待和恢复的原生支持

### 5.2 API 框架

最终选型：`FastAPI`

原因：

- Python 生态成熟
- 与 Pydantic 结合紧密
- 非常适合承载图片上传、回调 API、管理端查询 API
- 对后续 OpenAPI 文档、联调和部署都友好

### 5.3 不选通用 Agent SDK 作为主框架

最终结论：

- 不使用 `LangGraph` 作为主编排框架
- 不引入 `CrewAI`、`AutoGen` 一类多 Agent 框架作为基础架构
- 这类框架可以在未来局部用于“复杂提示链”或“开放风险解释”，但不进入系统主干

## 6. 可实现模块清单

以下模块按“先能跑起来，再逐步增强”的方式拆分。

### 6.1 接入层模块

#### `src/api/app.py`

职责：

- FastAPI 应用入口
- 路由注册
- 生命周期管理

#### `src/api/routes/ingestion.py`

职责：

- 接收机器狗图片与元数据
- 创建接入请求
- 返回同步初判结果或受理状态

#### `src/api/routes/events.py`

职责：

- 查询事件详情
- 查询某 `event_id` 的同步/异步阶段结果
- 查询人工复核状态

#### `src/api/schemas/`

职责：

- 请求/响应 Pydantic 模型
- `preliminary_event_feedback`
- `refined_event_feedback`
- `event_query_response`

### 6.2 编排层模块

#### `src/workflows/inspection_event_workflow.py`

核心工作流，职责：

- 接收 `frame_id` 和元数据
- 生成 `event_id`
- 编排同步初判
- 决定是否进入异步精检
- 编排 SAM3 分割
- 编排二次 VLM 审证
- 更新事件状态
- 触发同步/异步回传

这是系统最核心的一个模块。

#### `src/workflows/review_signal_workflow.py`

职责：

- 处理人工复核相关等待与恢复
- 接收后台管理服务或人工平台的审核信号
- 把复核结果推进到同一 `event_id`

如果第一期不做人工复核平台对接，可以先预留。

### 6.3 Activity 模块

#### `src/activities/preliminary_vlm_activity.py`

职责：

- 调用第一次 VLM
- 输出初判类别、风险等级、补拍建议、开放风险提示

#### `src/activities/sam3_evidence_activity.py`

职责：

- 调用 SAM3
- 生成 mask、bbox、叠图、裁剪图、面积比

#### `src/activities/evidence_judge_vlm_activity.py`

职责：

- 调用第二次 VLM
- 基于类目规则输出：
  - `evidence_basis_match`
  - `violation_relation_confirmed`
  - `exception_excluded`
  - `archive_readiness`

#### `src/activities/callback_activity.py`

职责：

- 统一调用 `SinkPlugin`
- 支持同步结果回传
- 支持异步结果回传

#### `src/activities/archive_activity.py`

职责：

- 存储原图、裁剪图、叠图、mask
- 写入数据库索引
- 生成 `evidence_package`

### 6.4 领域模型模块

#### `src/domain/events.py`

职责：

- 定义 `violation_event`
- 定义事件阶段与状态枚举

#### `src/domain/evidence.py`

职责：

- 定义 `evidence_package`
- 定义证据材料结构

#### `src/domain/taxonomy.py`

职责：

- 管理 9 个标准类目
- 管理每个类目的证据规则模板
- 管理例外条件模板

#### `src/domain/rules.py`

职责：

- 定义二次 VLM 复判模板输入结构
- 定义各类目证据锚点规范

### 6.5 基础设施模块

#### `src/infra/config.py`

职责：

- 加载 `agent_config.yaml`
- 管理环境变量与密钥

#### `src/infra/storage.py`

职责：

- 原图、mask、叠图、裁剪图存储
- 返回统一 URI

#### `src/infra/db/models.py`

职责：

- 数据库 ORM 模型
- 事件索引、证据索引、回传日志、审计日志

#### `src/infra/db/repositories/`

职责：

- `event_repository`
- `evidence_repository`
- `callback_repository`

#### `src/infra/temporal/`

职责：

- Temporal client
- worker 启动
- task queue 配置
- workflow/activity 注册

### 6.6 插件层模块

#### `src/plugins/base.py`

职责：

- 定义 `SinkPlugin` 抽象接口

#### `src/plugins/http_callback.py`

职责：

- HTTP 回传后台管理服务

#### `src/plugins/mq_callback.py`

职责：

- 消息队列方式回传

#### `src/plugins/grpc_callback.py`

职责：

- gRPC 方式回传

#### `src/plugins/factory.py`

职责：

- 按配置加载插件实现

### 6.7 模型适配层模块

#### `src/model_clients/vlm_client.py`

职责：

- 屏蔽 VLM 推理接口差异
- 统一超时、重试、结构化输出解析

#### `src/model_clients/sam3_client.py`

职责：

- 屏蔽 SAM3 推理接口差异
- 统一结果对象

### 6.8 运维与测试模块

#### `src/observability/logging.py`

职责：

- 结构化日志
- 绑定 `event_id`、`frame_id`、`workflow_id`

#### `src/observability/metrics.py`

职责：

- 同步时延
- 异步时延
- 回传成功率
- 类目命中率
- 人工复核率

#### `tests/unit/`

职责：

- 领域模型
- 配置加载
- 规则模板
- 插件工厂

#### `tests/integration/`

职责：

- 工作流端到端
- 同一 `event_id` 双链路更新
- 回传重试

## 7. 推荐的最小可运行版本

如果你要先做 MVP，我建议第一阶段只实现：

- `FastAPI`
- `Temporal`
- 一个 `InspectionEventWorkflow`
- 三个核心 Activity：
  - `preliminary_vlm_activity`
  - `sam3_evidence_activity`
  - `evidence_judge_vlm_activity`
- 一个 `http_callback` 插件
- PostgreSQL 事件索引
- 本地或 S3 兼容对象存储

先不做：

- 多种回传插件
- 复杂人工复核 UI
- 开放风险自动闭环
- 多工作流协同

## 8. 最终选型理由

最终选择 `Temporal + FastAPI`，而不是 `LangGraph + Celery` 或其他组合，理由很直接：

1. 你的主问题是可靠工作流，不是聊天 Agent 编排
2. 你需要一个事件贯穿同步和异步两条链路
3. 你需要天然支持重试、恢复、等待和回传补偿
4. 你不应该自己造“数据库状态机 + 任务队列 + 补偿逻辑”这一整套轮子
5. `FastAPI` 足够轻、成熟、对 Python 团队友好，适合做入口层
6. `Temporal` 则把最难、最容易踩坑的工作流可靠性问题接管掉

所以最终建议是：

- Agent 主编排框架：`Temporal`
- API/接入框架：`FastAPI`
- 不把通用 LLM Agent 框架放进主干

## 9. 实施顺序建议

建议实施顺序如下：

1. 建立项目骨架与配置系统
2. 建立 `FastAPI` 接入层
3. 建立 `Temporal` worker 与核心 workflow
4. 打通 VLM-1 / SAM3 / VLM-2 三个 Activity
5. 落地 `event_id` 共享和双阶段回传
6. 接入数据库与对象存储
7. 补测试、审计日志、异常重试

## 10. 待确认项

落实现阶段前仍建议确认：

- 你是否接受部署 Temporal Server
- 图片和证据文件是否走本地存储还是对象存储
- 后台管理服务更偏 HTTP、MQ 还是 gRPC
- 是否需要第一期就做人工复核信号回流
