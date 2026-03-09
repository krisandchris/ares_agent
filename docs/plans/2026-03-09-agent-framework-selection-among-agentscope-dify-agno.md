# 视觉巡检 Agent 框架选型（AgentScope / Dify / Agno）

## 1. 选型前提

本次只在以下 3 个候选项中选主框架：

- `AgentScope`
- `Dify`
- `Agno`

评价标准围绕当前项目需求，而不是泛化聊天 Agent：

- 多模态输入是否原生支持图片/视频/文件
- 是否方便封装自有 `VLM` 与 `SAM3`
- 是否适合“同步初判 + 异步精检 + 同一 event_id 更新”这种后端流程
- 是否能减少自研运行时、API 服务、状态管理、恢复机制的工作量
- 是否适合代码优先而不是纯画布优先的后端工程

## 2. 官方定位对比

### 2.1 AgentScope

AgentScope 官方 GitHub 将自己定义为：

- “Agent-Oriented Programming for Building LLM Applications”

其 README 强调：

- `Transparent to Developers`
- `Multi-Agent Oriented`
- `explicit message passing and workflow orchestration`
- `NO deep encapsulation`
- 支持 async execution、automatic state management、session/application-level state management、plan module

其文档还明确支持：

- 多模态消息块：`text`、`image`、`audio`、`video`、`file`

结论：

- AgentScope 是一个开发者控制力很强的代码优先 Agent 框架
- 很适合需要显式定义消息流、工作流和工具调用的复杂系统
- 对你这种“要把 VLM、SAM3、规则模板、回传流程全部握在自己手里”的场景很友好

### 2.2 Dify

Dify 官方 GitHub 将自己定义为：

- “Production-ready platform for agentic workflow development”

其 README 强调：

- intuitive interface
- agentic AI workflows
- RAG pipelines
- agent capabilities
- Backend-as-a-Service APIs

其文档和 README 也显示：

- 工作流以可视化 Canvas 为核心
- Agent node 支持 Function Calling 与 ReAct
- Workflow 支持图片上传
- Knowledge Retrieval 支持带 Vision 图标的 multimodal knowledge base 和图像检索

结论：

- Dify 是一个平台型产品，优势是低代码、工作流画布、运营和可视化配置
- 它适合快速搭 demo、运营型 AI 应用、RAG 和多模型应用编排
- 但对于你这种高度定制的视觉巡检后端，它更像“一个完整平台需要你去适配”，而不是“一个轻量可嵌入的 Agent 框架”

### 2.3 Agno

Agno 官方 GitHub 将自己定义为：

- “Build, run, manage multi-agent systems.”

其 README 把自己分成 3 层：

- Framework
- AgentOS Runtime
- Control Plane

它强调：

- `Async-first, built for long-running tasks`
- `Natively multimodal (text, images, audio, video, files)`
- `Type-safe I/O`
- `Ready-to-use FastAPI runtime`
- `Durable execution for resumable workflows`

Agno 官方文档还单独提供：

- multimodal overview
- multimodal agents
- multimodal teams

结论：

- Agno 不是只给你 Agent 类，而是给了框架、运行时和控制平面
- 对需要“尽快落一个可服务化后端”的项目更友好
- 它比 AgentScope 更偏“开箱即跑生产服务”

## 3. 结合本项目需求逐项判断

### 3.1 多模态能力

三者都支持多模态，但风格不同：

- `AgentScope`：多模态消息块和消息流最清晰，适合显式编排
- `Dify`：多模态更多体现在工作流节点、图片上传和多模态知识库
- `Agno`：多模态输入输出是 Agent/Team/Workflow 的原生能力

判断：

- 纯多模态能力上，`AgentScope` 和 `Agno` 更适合你的代码化后端

### 3.2 自有 VLM 与 SAM3 集成

你的核心不是调用公有模型，而是接已有：

- 巡检微调 VLM
- SAM3 分割模型

这要求框架必须方便封装本地/私有工具链。

判断：

- `AgentScope` 非常适合显式把模型封成 tool / workflow step
- `Agno` 也适合，且其 runtime 化更完整
- `Dify` 虽可通过插件和工具扩展，但整体更偏平台接入而非深度代码集成

### 3.3 同步 + 异步双链路

你的系统需要：

- 同步初判回传
- 异步精检回传
- 同一帧共享 `event_id`
- 异步链路更新同一事件

判断：

- `Dify` 的工作流画布可以表达流程，但这种“后端事件生命周期”并不是它最自然的问题形态
- `AgentScope` 能做，但你仍需自己补更多服务化和运行时管理
- `Agno` 直接把 runtime、FastAPI 服务和可恢复 workflow 放在主叙事里，更贴近这个需求

### 3.4 减少重复造轮子

这是你明确提出的目标。

判断：

- 如果选 `AgentScope`，你能获得很高控制力，但仍需要自己拼接更多服务层、API 层、运行时管理
- 如果选 `Dify`，你会得到大量平台能力，但会被平台形态和工作流画布约束
- 如果选 `Agno`，你能同时获得：
  - Agent/Workflow 框架
  - 现成 FastAPI runtime
  - durable execution
  - control plane

所以“少造轮子”这条上，`Agno` 最强

## 4. 最终结论

### 推荐选型：`Agno`

这是当前 3 个候选项中最适合作为你这个视觉巡检后端 Agent 主框架的方案。

原因：

1. 它原生支持多模态输入输出，直接适配图片/视频/文件类巡检输入
2. 它不仅是框架，还自带 `AgentOS Runtime` 和 `FastAPI runtime`
3. 它明确宣传 `durable execution for resumable workflows`，适合同步/异步双链路和长流程更新
4. 它是代码优先的，不会把你锁死在可视化平台中
5. 对你这种需要接入自有 `VLM` 和 `SAM3` 的项目，更像一个可落地后端基础设施，而不是一个演示平台

### 第二选择：`AgentScope`

当以下目标优先时，可以考虑改选 AgentScope：

- 你更看重开发者可控性和透明性
- 你希望消息流、工具流、工作流都显式写在代码里
- 你愿意自己补更多运行时和服务化层

AgentScope 很强，但更像“高可控的 Agent 编程框架”，不是“尽量少造轮子的全套后端支架”。

### 不推荐作为主框架：`Dify`

不是说 Dify 不好，而是它更适合：

- 低代码工作流搭建
- 多模态知识库/RAG 应用
- 运营和配置驱动型 AI 应用

不太适合作为你这个“高度定制的视觉巡检后端”的主干框架。

## 5. 对本项目的落地建议

如果采用 `Agno`，建议模块映射如下：

- `Agno Agent / Workflow`
  负责：
  - 同步初判
  - 异步精检
  - 二次 VLM 审证
  - 同一 `event_id` 生命周期推进

- `Agno AgentOS Runtime / FastAPI runtime`
  负责：
  - 图片接入 API
  - 查询 API
  - 后台管理服务回传接口

- 自定义 Tools / Functions
  负责：
  - `VLM-1` 调用
  - `SAM3` 调用
  - `VLM-2` 调用
  - 证据落盘
  - 回传插件

## 6. 关键保留意见

虽然本轮推荐 `Agno`，但有两个保留：

1. `Agno` 的 “durable execution” 与你需要的“同一事件多阶段严格审计”之间，仍建议后续做一次 PoC 验证
2. 如果你团队极度强调流程透明、完全掌控、弱平台依赖，那么 `AgentScope` 仍然是非常强的备选

## 7. 参考来源

- AgentScope GitHub: https://github.com/modelscope/agentscope
- AgentScope Docs:
  - https://doc.agentscope.io/v0/en/build_tutorial/message.html
  - https://doc.agentscope.io/build_tutorial/multimodality.html
- Dify GitHub: https://github.com/langgenius/dify
- Dify Docs:
  - https://docs.dify.ai/en/use-dify/nodes/agent
  - https://docs.dify.ai/en/guides/workflow/additional-features
  - https://docs.dify.ai/en/use-dify/nodes/knowledge-retrieval
- Agno GitHub: https://github.com/agno-agi/agno
- Agno Docs:
  - https://docs.agno.com/features/multimodal/overview
  - https://docs.agno.com/features/multimodal/agent/overview
