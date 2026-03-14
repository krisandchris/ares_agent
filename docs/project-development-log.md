# 项目开发日志

## 1. 文档目的

本文档用于沉淀当前 `ares_agent` 项目的开发脉络，基于会话期间持续维护的：

- `task_plan.md`
- `findings.md`
- `progress.md`

进行整理，形成一份面向项目本身、可长期保留的开发日志。

这份文档不是即时工作记忆，而是对阶段性研发过程的归档。

## 2. 项目起点

项目最初从近乎空白目录开始，没有现成代码或文档可直接继承。
用户已具备的核心资产只有两类模型能力：

- 巡检数据微调后的 `VLM`
- 用于违规证据实例分割的 `SAM3`

因此，早期工作的重点不在模型训练，而在于：

- 后端编排方式
- 服务链路设计
- 事件与证据结构
- 配置和测试基础设施

## 3. 设计阶段演进

### 3.1 体系结构收敛

项目最初围绕“城市街道巡检机器狗”的视觉后端 Agent 设计展开。
在多轮讨论后，架构从泛化的智能体设想逐步收敛成：

- 分层编排式后端
- 明确的状态推进
- `VLM-1 -> SAM3 -> VLM-2` 三段式处理
- preliminary / refined 双阶段结果
- callback 适配层

这一步明确了一个关键原则：

- 这是一个**强约束、可审计、可回放**的视觉巡检系统
- 不是自由式多 Agent 自治协作系统

### 3.2 框架选型收敛

框架选型经历了两轮收敛：

1. 先从一般工作流引擎角度比较
2. 后来按用户限定，只在：
   - `AgentScope`
   - `Dify`
   - `Agno`
   中做选择

最终项目选择了 `Agno` 作为框架基底，并用 `FastAPI` 暴露服务入口。

## 4. 第一阶段实现：MVP 闭环骨架

### 4.1 最小骨架搭建

这一阶段完成了：

- `pyproject.toml`
- `uv.lock`
- `src/ares_agent` 包布局
- `FastAPI` 入口
- `Agno workflow` 骨架
- 基础配置模型
- 事件 ID 生成

并从一开始就通过测试锁住核心约束：

- 同帧共享 `event_id`
- 配置可加载
- callback 基本链路可走通

### 4.2 Mock 闭环形成

随后逐步完成：

- fixture-backed `VLM-1`
- fixture-backed `SAM3`
- fixture-backed `VLM-2`
- `HttpCallbackPlugin`
- `/v1/inspection-items`
- `/v1/events/{event_id}`

到这一阶段，项目已经形成：

- `FastAPI -> Workflow -> Models -> Callback -> EventStore`

的 mock 闭环。

## 5. 第二阶段实现：契约收敛

### 5.1 输入契约调整

项目随后从初版输入收敛到更贴近真实机器狗采集方式的结构：

- 去掉 `frame_id`
- 引入 `camera_id`
- 引入 `location`

同时，`event_id` 生成策略同步调整为围绕：

- `image_uri`
- `camera_id`
- `location`
- `device_id`
- `task_id`
- `occur_time`

### 5.2 Prompt 架构收敛

提示词体系经历了多轮调整，最终形成：

- `camera_id + location` 只作为后端控制输入
- 通过 `scene_policies` 解析出场景语义
- `VLM-1` 直接看到的是：
  - `scene_hint`
  - `priority_categories`
  - `open_risk_guidance`
  - 优先类别定义摘要

同时将原来混在 prompt 里的全量类别定义拆出为：

- `category_registry`
- `open_risk_registry`

这让提示词与类别知识、场景策略之间的职责边界更清晰。

## 6. 第三阶段实现：服务形态与联调辅助

### 6.1 本地服务模拟

项目加入了本地 stub 服务，模拟真实部署形态：

- VLM preliminary endpoint
- VLM judge endpoint
- SAM3 segment endpoint

并新增 HTTP 风格 client，使得本地测试不仅能走 fixture，也能走“接近真实服务协议”的路径。

### 6.2 独立 VLM-1 Tester

为了不破坏主链路，同时又能高效调试 `VLM-1`，项目新增了独立的：

- `Gradio VLM-1 tester`

它专门负责：

- 输入 `camera_id + location`
- 展示场景策略
- 展示最终 prompt/messages
- 直接调用 `VLM-1`

而不会触发：

- `SAM3`
- `VLM-2`
- 主 workflow callback/event store

## 7. 第四阶段实现：服务模式与 MinIO/S3 支持

### 7.1 服务链路模式

项目后续引入了正式服务模式：

- `orchestrator.chain_mode: full`
- `orchestrator.chain_mode: vlm1_only`

并明确：

- `full`：同步跑完整三节点链路，HTTP 返回 `refined`
- `vlm1_only`：只跑 `VLM-1`，HTTP 返回 `preliminary`

### 7.2 分离配置

在服务化阶段，配置文件进一步拆分为：

- `service_config`
- `prompt_config`

其中：

- 服务配置负责：
  - callback
  - 模型地址
  - chain mode
  - MinIO
- prompt 配置负责：
  - scene policies
  - prompts
  - category registry

### 7.3 MinIO / S3 URI 解析

项目还新增了：

- `MinIOSettings`
- `image_uri_resolver`

支持：

- `http(s)` 对象 URL 原样透传
- `s3://bucket/key` 解析为 presigned URL

这样正式服务就可以在接收到 `s3://...` 后，在进入 `VLM-1` 或 `SAM3` 之前转成可访问的 `http(s)` URL。

## 8. 类型系统与工程清理

项目中后期有一大段工作都集中在：

- 清理 `Pylance` 类型噪音
- 收紧接口类型边界
- 用 `TypedDict`、`Mapping`、共享 payload 类型减少误报

这些工作覆盖了：

- workflow step content
- callback response
- API route return typing
- stored event payload
- prompt builders
- tester message typing
- HTTP model client payload typing
- shared JSON typing

这些改造虽然不改变业务功能，但显著提升了：

- 编辑器静态检查质量
- 配置与协议的可读性
- 后续维护成本

## 9. 当前阶段结论

到目前为止，项目已经形成一个较稳定的基线：

- `FastAPI` 接入
- `vlm1_only` / `full` 两种服务链路
- 配置驱动 prompt
- callback 语义清晰
- `s3://...` -> MinIO presigned URL 支持
- `Gradio VLM-1 tester`
- 较高覆盖率的单元测试
- 结构化链路日志
- 可选文件落盘 `event_store`
- VLM-1 多 candidate 输出
- 共享 `event_id` + 每个 candidate 的 `sub_event_id`
- per-candidate fan-out 到 `SAM3 -> VLM-2 -> callback`

当前仓库已经不再是最初的原型，而是一套结构明确、边界清晰、可继续推进真实联调的后端基线。

## 10. 最近新增能力

### 10.1 结构化日志

项目新增了基于 `structlog` 的结构化 JSON 日志，并接入：

- request lifecycle
- workflow stages
- model clients
- callback retry
- event store

日志关联方式为：

- `event_id` 作为根链路键
- `sub_event_id` 作为单 candidate 链路键
- `request_id` 作为 HTTP 层关联键

### 10.2 本地文件落盘 Event Store

项目新增了可选文件落盘 event store。

- 默认仍为内存态
- 配置为 `file` 时，会将根事件 payload 落到本地硬盘
- 文件路径以 `event_id` 为根键组织

### 10.3 多违规 Preliminary 与 Fan-Out

项目近期最大的协议变化，是将原来的“单类别 preliminary”扩展为：

- `VLM-1` 输出 `candidates[]`
- 每个 candidate 具备独立 `sub_event_id`
- 后续 `SAM3 / VLM-2 / callback` 仍保持单类别消费
- workflow 在 preliminary 之后执行 per-candidate fan-out

为了保持兼容：

- 顶层 root payload 仍保留首个 candidate 的兼容视图
- 完整多 candidate 结果通过 `sub_events` 提供

## 11. 开发日志维护原则

后续如果项目继续推进，建议：

1. `task_plan.md / findings.md / progress.md`
   继续作为本地工作记忆
2. 阶段性成果再整理回：
   - 本文档
   - 或 `docs/plans/` 下的专题文档

也就是说：

- planning files 负责“会话内工作记忆”
- `docs/project-development-log.md` 负责“项目阶段归档”
