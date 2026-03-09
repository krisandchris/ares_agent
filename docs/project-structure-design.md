# 项目结构设计文档

## 1. 文档目的

本文档说明当前 `ares_agent` 项目的目录结构、职责分层、核心数据流和扩展点。  
当前仓库定位为一个 `mocked closed-loop demo`，重点是验证：

- `FastAPI -> Workflow -> VLM-1 -> SAM3 -> VLM-2 -> callback`
- `SAM3` 与 `VLM-2` 的接口契约
- mock / http-stub / 配置驱动 启动方式

它不是最终的生产版城市街道巡检后端，但已经提供了一条结构清晰、可测试、可演进的主链路。

## 2. 顶层目录结构

```text
ares_agent/
├── config/
├── docs/
├── fixtures/
├── src/
├── tests/
├── README.md
├── pyproject.toml
└── uv.lock
```

各目录职责如下：

- `config/`
  运行配置样例。当前主要包含 `agent_config.example.yaml`，用于驱动 mock fixture、callback 和 prompt 模板。

- `docs/`
  设计文档目录。包含架构选型、后端设计、项目结构设计等文档。

- `fixtures/`
  本地 mock 样例数据。分别提供：
  - `mock_vlm_preliminary/`
  - `mock_sam3/`
  - `mock_vlm_judge/`

- `src/`
  项目主代码目录，采用 `src/ares_agent` 包布局。

- `tests/`
  当前以 `unit` 为主，但已经覆盖了多条接近集成级的 HTTP roundtrip 用例。

## 3. 代码分层

### 3.1 `src/ares_agent/api`

负责 HTTP 入口和 API schema。

- `app.py`
  应用入口，提供：
  - `/v1/inspection-items`
  - `/v1/events/{event_id}`
  - 本地 stub 模型接口

- `schemas.py`
  定义 API 请求/响应模型。

这一层只负责请求接入、响应封装和应用装配，不承载业务判断。

### 3.2 `src/ares_agent/workflows`

负责主链路编排。

- `inspection_event_workflow.py`
  是当前系统的核心。负责编排：
  - `VLM-1 preliminary`
  - `SAM3 segmentation`
  - `VLM-2 judge`
  - preliminary / refined callback

这层定义了当前的核心中间模型：

- `PreliminaryResult`
- `SegmentationResult`
- `EvidenceJudgeResult`

### 3.3 `src/ares_agent/model_clients`

负责模型访问适配。

- `mock_clients.py`
  直接从 JSON fixture 读取结果。

- `http_clients.py`
  模拟真实服务形态：
  - `SGLang/vLLM` OpenAI-compatible VLM
  - `FastAPI` 风格 SAM3

这一层的价值是把“模型协议”与“工作流编排”解耦。

### 3.4 `src/ares_agent/prompts`

负责 prompt 构造。

- `builders.py`
  当前已经区分：
  - `VLM-1` prompt
  - `VLM-2` prompt

其中 `VLM-1` 偏配置驱动，`VLM-2` 偏基于 `SAM3` 结果图和分割语义做审证提示。

### 3.5 `src/ares_agent/plugins`

负责结果回传。

- `http_callback.py`
  当前唯一实现，负责把 preliminary / refined 结果回传给后台管理服务。

### 3.6 `src/ares_agent/infra`

负责非业务基础设施。

- `config.py`
  配置加载与路径解析

- `event_store.py`
  当前是内存态事件仓库，用于保存最新事件结果

### 3.7 `src/ares_agent/domain`

负责领域对象和静态定义。

- `events.py`
- `evidence.py`
- `taxonomy.py`

## 4. 当前主链路

当前项目的主链路如下：

1. `POST /v1/inspection-items`
2. 解析 `image_uri + metadata`
3. 进入 `InspectionEventWorkflow`
4. `VLM-1` 输出：
   - `violation_category`
   - `segmentation_targets`
   - `relation_hint`
   - 以及环境分析字段
5. `SAM3` 接收：
   - `image_uri`
   - `targets`
6. `SAM3` 输出：
   - `overlay_image`
   - `mask_labels`
   - `relation_hint`
   - `segmentation_status`
   - `evidence_basis_summary`
7. `VLM-2` 消费：
   - `overlay_image`
   - `category_code`
   - `mask_labels`
   - `relation_hint`
   - `evidence_basis_summary`
8. callback 回传
9. 结果写入 `event_store`

## 5. 当前确定的设计约束

### 5.1 VLM-1

- 先分析环境，再给结论
- 输出标准化 JSON
- 为 `SAM3` 提供 `segmentation_targets`

### 5.2 SAM3

- 输入以 `image_uri` 为主
- 一次性接收候选词
- 不做多轮回退
- 若失败，按失败事件处理

### 5.3 VLM-2

- 以 `SAM3 overlay_image` 为主视觉输入
- 不再依赖原图链接继续往下传递
- prompt 重点字段为：
  - `category_code`
  - `mask_labels`
  - `relation_hint`
  - `evidence_basis_summary`

## 6. 当前缺口

当前结构已经稳定，但距离真实系统仍有明确缺口：

- 真实 `SGLang/vLLM` 客户端接入
- 真实 `SAM3 FastAPI` 接入
- 持久化数据库 / 对象存储
- callback 真正的超时重试
- 事件状态持久化
- 人工复核闭环

## 7. 结构演进建议

下一步如果走向真实系统，建议优先顺序：

1. 收敛 `PreliminaryResult` 为正式 schema
2. 切换 mock / real client 模式
3. 增加持久化 event store
4. 引入真实对象存储
5. 拆分 workflow 配置与运行配置

## 8. 结论

当前项目结构已经具备以下优点：

- 编排层、模型访问层、提示词层、回传层职责清晰
- 支持 mock 与 HTTP stub 两种联调方式
- 支持从 API 入口到工作流再到 callback 的闭环测试
- 后续接入真实模型服务时，不需要推翻整体结构

因此，这份结构适合作为当前版本的稳定基线。
