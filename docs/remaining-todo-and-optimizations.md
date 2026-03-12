# 剩余待办任务与优化点

## 1. 当前项目状态

当前仓库已经完成以下基线能力：

- `FastAPI` 接入层
- `Agno` 工作流主链路
- `VLM-1 -> SAM3 -> VLM-2 -> callback` mocked closed-loop demo
- `mock/http` 两种模型客户端模式
- 配置驱动的 prompt builder 与模型端点装配
- `VLM-1 / VLM-2` 的 `system/user` prompt 已统一放入 YAML，代码仅做变量注入
- in-memory `event_store`
- 事件查询接口
- 全量单测覆盖当前主链路

当前项目仍然是 `mocked closed-loop demo`，不是生产版后端。

当前版本已经有明确停止线：

- 不再扩展当前 MVP 的横向功能面
- 不再继续修改当前最小输入契约
- 不再回退当前 prompt 结构
- 后续工作应转入生产化主线，而不是继续给 MVP 叠功能

## 2. 剩余待办总览

建议把剩余工作分成 4 个层级：

1. 先完成协议与数据模型收敛
2. 再做真实服务联调
3. 再补持久化与可靠性
4. 最后补运营与审计能力

## 3. P2 级待办

这些是当前最适合继续推进的内容。

### 3.1 收敛 `VLM-1` 输出契约

虽然 `PreliminaryResult` 已经切到正式 schema，但仍需继续统一以下地方：

- `preliminary feedback` 对外字段是否最终保留当前最小集合
- `docs/` 中所有涉及初判输出的描述是否完全和代码一致
- `mock_vlm_preliminary` fixtures 是否扩充到所有标准类目

建议目标：

- 彻底只保留一套 `VLM-1` 输出 schema
- 不再出现任何历史兼容字段

### 3.2 收敛 `SAM3` 输入输出契约

当前代码已经切到：

- 输入：`image_uri + targets`
- 输出：`overlay_image + mask_labels + relation_hint + segmentation_status + evidence_basis_summary`

但仍建议进一步明确：

- `targets` 的最大数量
- `mask_labels` 的命名规范
- `segmentation_status` 枚举是否固定为 `ok / failed`

建议目标：

- 为 `SAM3` 定一版正式接口文档
- 后续真实服务联调时不再反复改字段

### 3.3 固化 `VLM-2` 输入契约

当前 `VLM-2` prompt 已收敛到：

- `category_code`
- `mask_labels`
- `relation_hint`
- `evidence_basis_summary`
- `overlay_image`

剩余待办：

- 把这版契约整理成正式文档
- 明确哪些字段是必须、哪些字段允许为空
- 确定 `segmentation_status=failed` 时是否完全跳过 `VLM-2`

### 3.4 固化 prompt 模板接口

当前 prompt 契约已经收敛为：

- `prompts.preliminary.system`
- `prompts.preliminary.user`
- `prompts.judge.system`
- `prompts.judge.user`

仍建议补充：

- 明确 `VLM-1 user` 允许使用的变量集合，当前默认不注入采集元数据
- 明确 `VLM-2 user` 允许使用的变量集合，仅限：
  - `category_code`
  - `mask_labels`
  - `relation_hint`
  - `evidence_basis_summary`
- 明确 `overlay_image` 和原图这类多模态输入始终通过 image content 传递，而不是模板变量

## 4. 真实联调待办

### 4.1 真实 `SGLang/vLLM` 联调

当前代码已经支持配置：

- `base_url`
- `endpoint`
- `model_name`
- `timeout_ms`
- `temperature`
- `max_tokens`

但仍缺：

- 实际请求/响应日志验证
- 真实模型返回 JSON 稳定性校验
- 非法 JSON/字段缺失时的降级处理

### 4.2 真实 `SAM3 FastAPI` 联调

当前已支持 `image_uri + targets` 的 HTTP 调用，但仍缺：

- 实际响应 schema 与当前 mock 契约比对
- 图像读取失败、空掩码、部分掩码等真实异常处理
- overlay 图和 mask label 的一致性验证

### 4.3 mode=http 的默认运行路径

当前 `mode=http` 已能在测试中跑通，但还需要：

- README 中增加真实联调示例配置
- 增加“真实模式启动”命令示例
- 区分 mock 模式与真实模式的部署说明

## 5. 持久化与可靠性待办

### 5.1 持久化事件存储

当前是 `InMemoryEventStore`，只适合 demo。

后续应替换为：

- PostgreSQL 或其他持久化数据库

需要至少保存：

- `event_id`
- 原始请求元数据
- preliminary 结果
- SAM3 结果摘要
- refined 结果
- callback 状态

### 5.2 callback 可靠性

当前 `HttpCallbackPlugin` 已支持配置字段，但还没做真正可靠实现：

- retry loop
- backoff
- timeout
- 失败落库
- 幂等控制

### 5.3 对象存储

当前只是 URI 级模拟。

后续需要：

- 原图存储
- overlay 图存储
- crop 图存储
- mask 存储

## 6. 审计与可观测性优化

### 6.1 结构化日志

建议补：

- `event_id`
- `frame_id`
- `stage`
- `category_code`
- `callback_status`

### 6.2 指标

建议补：

- preliminary 成功率
- segmentation 成功率
- VLM-2 审证成功率
- callback 成功率
- 平均耗时

### 6.3 审计记录

建议补：

- VLM-1 原始输出
- SAM3 结果摘要
- VLM-2 判定结果
- callback 历史

## 7. 代码结构优化点

### 7.1 `PreliminaryResult` / `SegmentationResult` / `EvidenceJudgeResult` 下沉到 `domain`

当前这三个模型还在 `workflows/inspection_event_workflow.py` 中。

建议后续拆出到：

- `src/ares_agent/domain/preliminary.py`
- `src/ares_agent/domain/segmentation.py`
- `src/ares_agent/domain/judgment.py`

这样会更清晰，也更利于复用。

### 7.2 `mock` 与 `real-http` 模式的工厂再拆分

当前装配逻辑主要在 `api/app.py`。

建议后续拆出：

- `src/ares_agent/infra/bootstrap.py`
- `src/ares_agent/model_clients/factory.py`

### 7.3 prompt builder 再细分

当前 `prompts/builders.py` 同时负责：

- 默认 builder
- 配置驱动 builder
- 模板变量注入

建议后续按阶段拆成：

- `preliminary_builder`
- `judge_builder`
- `template_rendering`

## 8. 不建议现在优先做的事

下面这些现在不适合优先推进：

- 继续增加更多 mock feature
- 引入人工复核工作流
- 引入过重的多 agent 协作层
- 一边做真实联调一边改 schema

原因是当前更需要的是“先把协议锁住、真实链路跑通”。

## 9. 建议的后续顺序

建议顺序如下：

1. 固化 `VLM-1 / SAM3 / VLM-2` 三段接口文档
2. 跑通真实 `mode=http` 联调
3. 上持久化事件存储
4. 完成 callback 可靠性
5. 再补日志、指标、审计

## 10. 当前结论

当前仓库最值得继续做的不是再加功能，而是：

- 锁协议
- 接真实服务
- 补持久化
- 补可靠性

这四件事完成后，项目才会从 `mocked closed-loop demo` 真正进入“可外部联调的后端 MVP”。
