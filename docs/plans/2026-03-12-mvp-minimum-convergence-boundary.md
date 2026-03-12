# MVP 最小收敛边界

## 1. 文档目的

本文档用于明确当前 `ares_agent` 仓库在 MVP 阶段的**最小收敛边界**，回答两个问题：

1. 当前版本到底收敛到哪里为止
2. 哪些内容不再属于当前 MVP 继续扩展的范围

这份文档的作用不是列更多规划，而是给当前版本划出一条明确的停止线。

## 2. 当前版本定位

当前版本定位为：

- `camera/location-aware mocked closed-loop demo`

它不是生产后端，但已经不是早期原型。  
它的最小目标是验证：

- `v1/inspection-items` 输入契约是否稳定
- `camera_id + location` 场景策略是否能稳定影响 `VLM-1`
- `VLM-1 -> SAM3 -> VLM-2` 主链路是否闭环
- preliminary / refined 是否共享同一 `event_id`
- callback / event_store / query 是否能形成最小结果闭环

## 3. 当前 MVP 的最小闭环

当前收敛后的最小链路如下：

1. `POST /v1/inspection-items`
2. 请求体校验：
   - `image_uri`
   - `camera_id`
   - `location`
   - `device_id`
   - `task_id`
   - `occur_time`
3. 后端根据 `camera_id + location` 解析场景策略
4. `VLM-1` 进行结构化初判
5. `SAM3` 进行一次性分割
6. `VLM-2` 基于分割结果图做审证
7. preliminary / refined callback
8. 结果写入 `event_store`
9. `GET /v1/events/{event_id}` 查询事件结果

这条链路是当前 MVP 的核心闭环，不再继续缩减。

## 4. 当前版本已经收敛的最小特性

### 4.1 输入契约收敛

当前输入契约已经收敛为：

- `image_uri`
- `camera_id`
- `location`
- `device_id`
- `task_id`
- `occur_time`

这一版不再继续改输入字段。

### 4.2 事件主键收敛

`event_id` 已围绕以下稳定字段生成：

- `image_uri`
- `camera_id`
- `location`
- `device_id`
- `task_id`
- `occur_time`

当前版本要求：

- preliminary 与 refined 必须共享同一 `event_id`
- 失败事件也必须保留同一事件主键语义

### 4.3 `VLM-1` 提示词结构收敛

`VLM-1` 提示词已经收敛成以下结构：

- prompt skeleton
- `scene_policies`
- `category_registry`
- `open_risk_registry`

其中：

- `camera_id + location` 只作为后端控制输入
- 不直接进入 prompt
- `VLM-1` 直接看到的是：
  - `scene_hint`
  - `priority_categories`
  - `open_risk_guidance`
  - 当前优先类别定义摘要

这一版不再回退到“大而全的单段 system prompt”。

### 4.4 `SAM3` 契约收敛

当前 `SAM3` 最小接口收敛为：

- 输入：
  - `image_uri`
  - `targets`
- 输出：
  - `overlay_image`
  - `mask_labels`
  - `relation_hint`
  - `segmentation_status`
  - `evidence_basis_summary`

当前 MVP 下，不再继续扩展更复杂的回退分割策略。

### 4.5 `VLM-2` 审证输入收敛

`VLM-2` 当前最小输入已经收敛为：

- `category_code`
- `mask_labels`
- `relation_hint`
- `evidence_basis_summary`
- `overlay_image`

其中：

- `overlay_image` 是主视觉输入
- 不再继续传原图给 `VLM-2`

### 4.6 配置边界收敛

当前配置层已经具备最小可控性：

- callback 阶段开关合法性校验
- `scene_policies` 对 `category_registry` 的引用校验
- `mode=mock/http` 的模型装配路径

这说明当前 MVP 已具备“配置驱动 + 启动期失败”的最小工程约束。

## 5. 当前 MVP 明确不再扩展的内容

以下内容不属于当前 MVP 收敛范围：

- 人工复核闭环
- 持久化数据库
- 对象存储
- RAG 类别知识库
- 更复杂的 scene policy DSL
- 更多 callback/plugin 类型
- 运营审计后台
- 真实生产级可观测性
- 更复杂的工作流分支

这些内容应进入下一阶段，而不是继续塞进当前 MVP。

## 6. 当前收敛基线的验证标准

当前版本可视为达到 MVP 最小收敛，至少需要满足：

1. `v1/inspection-items` 契约稳定
2. `camera_id + location` 能稳定影响 `VLM-1` prompt 结果
3. `VLM-1 -> SAM3 -> VLM-2` 闭环稳定
4. preliminary / refined / failed 事件生命周期稳定
5. 结果可 callback、可入库、可查询
6. 单元测试全绿

当前验证基线：

- `uv run pytest tests/unit`

## 7. 收敛结论

当前项目的最小收敛结论是：

- 它已经具备一个**稳定的、场景感知的、可配置的视觉巡检闭环 demo 后端**
- 它还不是生产系统
- 它当前最重要的任务不再是“继续补更多功能”
- 而是以当前边界为基线，转入下一阶段的生产化建设

## 8. 后续工作原则

从本版本开始，后续工作应遵循：

1. 不再扩展当前 MVP 的横向功能面
2. 不再继续修改当前最小输入契约
3. 不再回退 prompt 结构
4. 下一阶段只围绕生产化主线推进：
   - 持久化
   - 真实模型联调
   - 人工复核
   - 可观测性与审计
