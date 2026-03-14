# 多违规 Preliminary 设计方案

## 1. 目标

让 VLM-1 在单张图中输出多个违规候选，但保持下游 `SAM3 -> VLM-2 -> callback -> event_store` 仍按单个类别逐条处理。

## 2. 当前约束

当前系统是单类别协议：

- `PreliminaryResult.violation_category` 是单个字符串
- `preliminary_feedback.violation_category` 是单个字符串
- VLM-2 只接收一个 `category_code`
- refined feedback 只输出一个 `final_category`

因此，多违规支持不能只改 prompt，必须扩展 preliminary 输出协议和 workflow fan-out。

## 3. 推荐方案

推荐把 VLM-1 输出改成“候选列表”，下游对每个 candidate 单独执行现有链路。

### 3.1 新的 VLM-1 输出形态

顶层 preliminary 输出不再只有一个 `violation_category`，而是：

- `environment_analysis`
- `scene_elements`
- `candidates: list[PreliminaryCandidate]`

每个 `PreliminaryCandidate` 包含：

- `candidate_rank`
- `violation_category`
- `open_risk_type`
- `confidence`
- `evidence_reasoning`
- `segmentation_targets`
- `relation_hint`

这样 VLM-1 的职责变为：

1. 识别图中所有值得进入下游复核的候选违规
2. 为每个候选给出单独的分割目标和关系提示

## 4. Workflow Fan-Out

推荐增加一个 `candidate_dispatch` 阶段：

1. `preliminary_multi`
2. `candidate_dispatch`
3. 对每个 candidate 复用现有：
   - `segmentation`
   - `evidence_judge`
   - `callback`
   - `event_store`

关键原则：

- 下游完全保持“单 candidate 消费”
- 每个 candidate 独立执行现有 SAM3/VLM-2 判定
- preliminary 只负责列出候选，不再试图一次性完成最终裁决

## 5. 事件模型建议

当前 `event_id` 基于图像和元数据稳定生成，已经适合继续作为整张图的根事件键。

本方案不修改现有 `event_id` 语义和生成逻辑，只新增：

- `sub_event_id`
  - 表示某个候选违规子事件
  - 用于下游单类别链路和子结果追踪

建议生成方式：

- `event_id = generate_event_id(seed)`
- `sub_event_id = hash(event_id + violation_category + candidate_rank)`

这样可以保证：

- 同一图的多个违规仍共享同一个 `event_id`
- 每个 candidate 有独立 `sub_event_id`
- 现有依赖 `event_id` 的接口与检索逻辑不需要整体迁移

## 6. Callback / Event Store 适配

### Callback

建议 preliminary callback 不再只发单个 `violation_category`，而是发：

- `event_id`
- `stage=preliminary`
- `candidate_count`
- `candidates_summary`

而 refined callback 仍按单 candidate 发送：

- `event_id`
- `sub_event_id`
- `final_category`

### Event Store

建议演进为：

- 根事件文件/记录：保存整张图的 preliminary candidates 汇总
- 子事件文件/记录：保存每个 candidate 的 refined 结果

## 7. Prompt 设计原则

VLM-1 prompt 需要从“单类别单结论”改成“多 candidate 有序输出”。

应新增明确规则：

- 输出所有显著且可区分的违规候选
- 候选之间不能重复表达同一现象
- 候选按证据显著性排序
- 若多个类别共享同一组视觉证据，优先输出更具体类别
- 若无法区分多个相近类别，只输出最可信一个

这意味着多违规支持必须靠输出 contract 明确约束，不能靠模型自由发挥。

## 8. 兼容迁移策略

建议分两步做：

### Phase A

先引入新 schema，但把 candidate 数量限制为 `0..1`，确认兼容链路可跑通。

### Phase B

再放开 `candidates > 1`，引入 fan-out、root/candidate 双层 id、callback 和 event store 适配。

## 9. 为什么推荐这个方案

这个方案的优点是：

- 复用现有单类别下游能力
- 降低一次性改动风险
- 清晰区分“候选生成”和“证据复核”
- 为未来真正的多事件处理打下协议基础

它的代价是：

- workflow 会从单链路变成 fan-out
- id 模型会复杂一些
- callback / event_store 需要新增根事件与子事件关系

但相比“让 VLM-1 直接拼接多个类别到一个字段里”，这是唯一结构上稳定、可测试、可演进的路线。
