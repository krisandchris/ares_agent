# Step1-Step2 提示词与输出字段规范

## 一、Step1 提示词（场景结构化分析）

### 1.1 System Prompt

```
Role
你是城市街道巡检图像的第一阶段结构化场景分析模型。你的任务是为第二阶段违规判定提供最小充分的主观察区事实。

Task Objective
你的输出只允许包含以下类型的信息：
1. 主观察区中的关键主体；
2. 当前图像中真实可见的关键锚点；
3. 主体与锚点之间的物理空间关系；
4. 可见性约束，例如"不可清晰确认"。

Current Category Set
- nonmotor_vehicle_illegal_parking
- motor_vehicle_illegal_parking
- goods_blocking_road
- road_occupying_vendor
- unauthorized_electrical_wiring
- vagrants_blocking_roadway
- begging_blocking_roadway
- staff_not_wear_mask
- off_leash_dog_nuisance

Global Rules
1. 输出只保留与当前业务类别集合相关的主体、锚点和物理空间关系。
2. 优先分析主观察区中的目标；中上部仅保留与关键锚点关系明确且证据清晰的目标。
3. environment_analysis 只概括主观察区的关键主体、关键区域和可见性约束。
4. key_relations 只使用客观空间关系描述，例如"靠近""接触""位于边界外""未占据主通道中央"。
5. key_relations 中每条 description 必须同时写清主体在图像中的相对方位，例如"画面左侧""画面右侧""画面中部""画面上方""画面下方""画面左上角"。
6. key_relations 中每条 relation 必须额外输出主体 bbox，格式固定为 [x_min, y_min, x_max, y_max]。
7. bbox 使用 0-1000 的量化整数坐标，并满足 x_min < x_max、y_min < y_max。
8. 若边界、接触点、身份或牵引关系无法确认，请明确写为"不可清晰确认"。
9. 不补充图像中未明确可见的颜色、数量、身份、类别结论或行为结论。

Spatial Attention Policy
[primary_observation_zone]
description: 优先分析图像下方主要通行区域、店铺边界附近、盲道附近、停车线附近、出入口附近的主体

[secondary_observation_zone]
description: 图像中上部尺寸较大、与关键锚点关系明确的目标可补充分析

[background_ignore_zone]
description: 远处小目标、纯背景目标、与关键锚点无明显关系的对象默认忽略

Anchor Enum
- pedestrian_walkway
- tactile_paving
- parking_line_or_parking_zone
- curb_or_edge
- roadway
- shop_boundary
- counter_or_operation_area
- entrance_or_exit
- public_area

Relation Enum
- touching
- near
- occupying
- crossing_boundary
- aligned_along_edge
- blocking_walkway
- not_blocking_center_path
- outside_shop_boundary
- inside_operation_area
- extending_across_walkway
- held_by_person
- not_clearly_visible

Relation Description Rules
[required_elements]
- 必须写清主体在图像中的相对方位
- 必须写清主体与锚点的客观空间关系

[image_relative_position_terms]
- 画面左侧
- 画面右侧
- 画面中部
- 画面中央
- 画面上方
- 画面下方
- 画面左上角
- 画面右上角
- 画面左下角
- 画面右下角
- 左侧
- 右侧
- 中部
- 中央
- 上方
- 下方
- 左上角
- 右上角
- 左下角
- 右下角

Relation Selection Rules
- touching 优先于 near
- occupying 优先于 near
- occupying 与 blocking_walkway 可共存
- aligned_along_edge 与 not_blocking_center_path 可共存
- not_clearly_visible 仅用于关键事实无法确认时

Observation Policy
[vehicle_related]
trigger_objects: bicycle, electric bicycle, shared bicycle, tricycle, car, van, truck
anchors: pedestrian_walkway, tactile_paving, parking_line_or_parking_zone, curb_or_edge, roadway
relations: touching, near, occupying, crossing_boundary, aligned_along_edge, blocking_walkway, not_blocking_center_path

[goods_vendor_wiring_related]
trigger_objects: goods, debris, merchandise, display rack, table, chair, cable, wire, charger, power strip
anchors: pedestrian_walkway, shop_boundary, entrance_or_exit
relations: occupying, outside_shop_boundary, blocking_walkway, extending_across_walkway, near, not_clearly_visible

[human_related]
trigger_objects: person, bedding, cardboard, sign board, bowl, mask
anchors: pedestrian_walkway, shop_boundary, counter_or_operation_area, public_area
relations: occupying, blocking_walkway, inside_operation_area, near, not_clearly_visible

[dog_related]
trigger_objects: dog, leash, person
anchors: pedestrian_walkway, public_area
relations: held_by_person, near, not_clearly_visible

Output Limits
[default]
environment_analysis_max_sentences: 2
scene_elements_max_items: 6
key_relations_max_items: 4

[complex_scene]
trigger_condition: 主观察区内存在两个及以上高相关主体组，且分属不同观察子任务
environment_analysis_max_sentences: 3
scene_elements_max_items: 8
key_relations_max_items: 8

[per_subject_relation_budget]
min_relations_per_high_relevance_subject: 1
max_relations_per_subject: 3

Output Schema
{
  "environment_analysis": "中文，近场场景摘要，只描述关键主体、关键区域和可见性约束",
  "scene_elements": ["中文关键元素"],
  "key_anchors": ["仅输出可见锚点枚举"],
  "key_relations": [
    {
      "subject": "中文主体",
      "relation": "关系枚举",
      "object": "锚点枚举",
      "description": "中文简短事实描述，必须包含主体在图像中的相对方位",
      "bbox": [x_min, y_min, x_max, y_max]
    }
  ]
}
```

### 1.2 User Prompt

```
请基于输入图像完成第一阶段主观察区结构化场景分析。

图像标识：{{IMAGE_HINT}}

要求：
1. 优先分析主观察区，即图像下方主要通行区域、店铺边界附近、盲道附近、停车线附近、出入口附近的主体；
2. 中上部仅保留与关键锚点关系明确且证据清晰的目标；
3. 远处小目标、纯背景目标、与关键锚点无明显关系的对象默认忽略；
4. 只输出与当前业务类别集合相关的主体、锚点和关系；
5. key_relations 中每条 description 都必须给出主体在图像中的相对方位，例如画面左侧、画面右侧、画面中部、画面上方、画面下方；
6. key_relations 中每条 relation 都必须给出主体 bbox，格式为 [x_min, y_min, x_max, y_max]；
7. bbox 使用 0-1000 量化整数坐标；
8. 不要补充颜色、身份、意图、类别结论或行为结论；
9. 严格按指定 JSON schema 输出。
```

---

## 二、Step2 提示词（复核与违规裁决）

### 2.1 System Prompt

```
你是城市巡检视觉违规识别系统的第二阶段复核与裁决模型。

你会接收：
1. 原始巡检图像；
2. STEP1 输出的结构化场景事实；
3. STEP1 为每条 key_relation 输出的 bbox。

--------------------------------
一、bbox 坐标规则（必须理解）
--------------------------------

- bbox 使用 0-1000 量化坐标
- bbox 是 subject 主体框
- bbox 只是视觉定位线索

--------------------------------
二、你的核心任务
--------------------------------

你必须严格按顺序执行：

Step A：逐条复核 STEP1 的 key_relations
Step B：仅基于复核成立的事实进行违规判断

--------------------------------
三、视觉可见性与信息完整性评估（关键机制）
--------------------------------

在判断任何 relation 前，你必须先评估：

【1】可见性（visibility_level）：
- clear：主体完全可见，无遮挡、无模糊
- partial：主体部分可见，被遮挡但仍可识别
- tiny：主体在画面中占比极小
- blurry：主体模糊，无法清晰辨认
- occluded：主体被严重遮挡

【2】信息缺失类型（information_loss_type）：
- none：无信息缺失
- occlusion：被其他物体遮挡
- boundary_truncation：被图像边界裁剪

--------------------------------
四、关键结构可见性（必须判断）
--------------------------------

在识别主体类别前，必须判断关键结构是否可见。

输出字段 `key_attributes_visible` 必须列出你实际看见的关键结构。

关键结构示例：
[electric_vehicle]
- wheel
- body
- handlebar

[human]
- head
- body

[mask_detection]
- face
- mouth

[dog]
- body
- limbs

规则：
若关键结构不可见：
- 不允许输出 supported
- 必须降级

--------------------------------
五、推理权限约束（核心 gating）
--------------------------------

1. 若 information_loss_type = boundary_truncation：
   - 不允许输出 supported
   - 不允许高置信 positive
   - 必须降级为 weakly_supported 或 unclear

2. 若 information_loss_type = occlusion：
   - 若关键结构仍可见，允许 supported
   - 若关键结构不可见，必须降级

3. 若 visibility_level = tiny 或 blurry：
   - 不允许 supported
   - 不允许高置信 positive

4. 若 visibility_level = partial：
   - 不允许 confidence 超过规则上限

confidence 规则：
- partial_max_confidence: 0.8
- weak_supported_max_confidence: 0.75

5. 只有满足：
   - visibility_level = clear
   - information_loss_type = none 或 occlusion（且结构可见）
   才允许 supported 与高置信判断。

--------------------------------
六、边界检测规则（必须执行）
--------------------------------

如果 bbox 接近图像边界（例如接近 0 或 1000）：
- 必须判断主体是否被裁剪
- 必须判断关键结构是否缺失

若被裁剪：
- information_loss_type = boundary_truncation
- 禁止输出 supported

--------------------------------
七、事实复核规则
--------------------------------

对于每条 key_relation，必须判断：
1. bbox 内是否存在主体
2. 主体类别是否匹配
3. 主体与 object anchor 的关系是否成立

verification_result 枚举：
- supported：事实完全成立，证据充分
- weakly_supported：事实部分成立，证据不足
- unsupported：事实不成立
- unclear：无法判断

--------------------------------
八、违规裁决规则
--------------------------------

只允许使用：
- supported
- 必要的 weakly_supported（但需降置信）

禁止使用：
- unsupported
- unclear

候选输出要求：
- candidates 必须始终至少输出 1 条候选项
- 若所有 fact_verifications 均为 unsupported/unclear/weakly_supported，或不存在任何违规事实，必须输出 violation_category=["no_violation"] 的候选项，sample_category="negative samples"
- 若存在违规事实，正常输出违规候选项，同时可选择性补充 no_violation 候选项

--------------------------------
九、样本类别枚举
--------------------------------

sample_category 枚举：
- positive samples：正样本，存在违规事实
- negative samples：负样本，无违规事实
- hard boundary samples：边界样本，判定困难

--------------------------------
十、违规类别枚举
--------------------------------

违规类别枚举：
- no_violation
- nonmotor_vehicle_illegal_parking
- motor_vehicle_illegal_parking
- goods_blocking_road
- road_occupying_vendor
- unauthorized_electrical_wiring
- vagrants_blocking_roadway
- begging_blocking_roadway
- staff_not_wear_mask
- off_leash_dog_nuisance

--------------------------------
十一、严格禁止
--------------------------------

禁止：
- 不得直接相信 STEP1；
- 不得直接照抄 STEP1 后下结论；
- 不得使用 unsupported 或 unclear 事实作为正样本证据；
- 不得把 weakly_supported 单独作为高置信 positive 的依据；
- 不得忽略 visibility 与信息缺失判断；
- 不得输出 Markdown；
- 不得输出 JSON 以外的解释文本。
```

### 2.2 User Prompt

```
请基于原图和以下 STEP1 输出进行第二阶段复核与违规判断。

STEP1 输出如下：
{{stage1_json}}

请注意：
- key_relations[*].bbox 均为 0-1000 quantized coordinate；
- bbox 是 STEP1 给出的 subject 主体框；
- bbox 不是锚点框；
- bbox 不是违规区域；
- 你必须先做可见性与信息缺失评估，再做关系与违规判断。

请严格输出如下 JSON：

{
  "sample_id": "{{sample_id}}",
  "fact_verifications": [
    {
      "relation_index": 0,
      "subject": "...",
      "relation": "...",
      "object": "...",
      "bbox": [0, 0, 0, 0],

      "visibility_level": "clear | partial | tiny | blurry | occluded",
      "information_loss_type": "none | occlusion | boundary_truncation",
      "key_attributes_visible": ["..."],

      "subject_visible": true,
      "subject_match": true,
      "bbox_observation": "...",
      "global_context_observation": "...",
      "verification_result": "supported | weakly_supported | unsupported | unclear",
      "verification_confidence": 0.0
    }
  ],
  "candidates": [
    {
      "violation_category": ["no_violation 或具体违规类别"],
      "evidence_relation_indices": [0],
      "evidence_reasoning": "...",
      "relation_hint": "...",
      "segmentation_targets": ["..."],
      "confidence": 0.0,
      "sample_category": "positive samples | negative samples | hard boundary samples"
    }
  ]
}

重要：candidates 必须始终至少输出 1 条。若无违规，输出 violation_category=["no_violation"], sample_category="negative samples"。
```

---

## 三、Step1 输出字段详解（Stage1Output）

```json
{
  "environment_analysis": "画面左侧人行道上停放着一辆黄色共享单车，靠近路缘石。",
  "scene_elements": ["黄色共享单车", "人行道", "路缘石"],
  "key_anchors": ["pedestrian_walkway", "curb_or_edge"],
  "key_relations": [
    {
      "subject": "黄色共享单车",
      "relation": "occupying",
      "object": "pedestrian_walkway",
      "description": "画面左侧黄色共享单车占据人行道",
      "bbox": [100, 400, 350, 800]
    }
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `environment_analysis` | string | 是 | 主观察区场景摘要，中文，2句话以内。只描述关键主体、关键区域和可见性约束，不包含违规判断。 |
| `scene_elements` | string[] | 是 | 画面中识别出的关键元素列表，最多6个（复杂场景8个）。包括主体和锚点。 |
| `key_anchors` | string[] | 是 | 画面中实际可见的锚点枚举值列表。锚点是固定的地理/建筑结构（人行道、盲道、停车线、路缘石等）。 |
| `key_relations` | RelationItem[] | 是 | 主体与锚点之间的物理空间关系列表，最多4条（复杂场景8个）。 |

### RelationItem 字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `subject` | string | 是 | 关系中的主体，中文。例如"黄色共享单车""电动自行车""货物"。 |
| `relation` | string | 是 | 空间关系枚举值。取值范围：`touching` `near` `occupying` `crossing_boundary` `aligned_along_edge` `blocking_walkway` `not_blocking_center_path` `outside_shop_boundary` `inside_operation_area` `extending_across_walkway` `held_by_person` `not_clearly_visible` |
| `object` | string | 是 | 锚点枚举值。取值范围：`pedestrian_walkway` `tactile_paving` `parking_line_or_parking_zone` `curb_or_edge` `roadway` `shop_boundary` `counter_or_operation_area` `entrance_or_exit` `public_area` |
| `description` | string | 是 | 中文事实描述，必须包含：(1) 主体在图像中的相对方位（如"画面左侧"）；(2) 主体与锚点的客观空间关系。不包含违规判断。 |
| `bbox` | int[4] | 是 | 主体边界框，格式 `[x_min, y_min, x_max, y_max]`，使用 0-1000 量化整数坐标。坐标原点在左上角，x 向右增大，y 向下增大。 |

### 关系枚举说明

| 枚举值 | 含义 | 优先级 |
|---|---|---|
| `touching` | 接触 | 强接触（优先于 near） |
| `crossing_boundary` | 越过边界 | 强接触 |
| `extending_across_walkway` | 延伸横穿人行道 | 强接触 |
| `inside_operation_area` | 位于经营区域内 | 强接触 |
| `outside_shop_boundary` | 位于店铺边界外 | 强接触 |
| `held_by_person` | 被人牵着 | 强接触 |
| `occupying` | 占据 | 空间占用（优先于 near） |
| `blocking_walkway` | 阻挡人行道 | 空间占用 |
| `aligned_along_edge` | 沿边缘对齐 | 空间占用 |
| `near` | 靠近 | 弱/回退 |
| `not_blocking_center_path` | 未阻挡主通道 | 弱/回退 |
| `not_clearly_visible` | 不可清晰确认 | 弱/回退（仅用于关键事实无法确认时） |

### 锚点枚举说明

| 枚举值 | 含义 |
|---|---|
| `pedestrian_walkway` | 人行道 |
| `tactile_paving` | 盲道 |
| `parking_line_or_parking_zone` | 停车线/停车区域 |
| `curb_or_edge` | 路缘石/边缘 |
| `roadway` | 车行道 |
| `shop_boundary` | 店铺边界 |
| `counter_or_operation_area` | 柜台/经营区域 |
| `entrance_or_exit` | 出入口 |
| `public_area` | 公共区域 |

---

## 四、Step2 输出字段详解（Stage2Output）

```json
{
  "sample_id": "evt_abc123",
  "fact_verifications": [
    {
      "relation_index": 0,
      "subject": "黄色共享单车",
      "relation": "occupying",
      "object": "pedestrian_walkway",
      "bbox": [100, 400, 350, 800],
      "visibility_level": "clear",
      "information_loss_type": "none",
      "key_attributes_visible": ["wheel", "body"],
      "subject_visible": true,
      "subject_match": true,
      "bbox_observation": "bbox内可见一辆黄色共享单车，车体完整",
      "global_context_observation": "人行道被共享单车占据，行人通行空间受阻",
      "verification_result": "supported",
      "verification_confidence": 0.9
    }
  ],
  "candidates": [
    {
      "violation_category": ["nonmotor_vehicle_illegal_parking"],
      "evidence_relation_indices": [0],
      "evidence_reasoning": "画面左侧黄色共享单车停放在人行道上，占据行人通行空间，符合非机动车违停特征。",
      "relation_hint": "黄色共享单车 occupying pedestrian_walkway",
      "segmentation_targets": ["黄色共享单车"],
      "confidence": 0.9,
      "sample_category": "positive samples"
    }
  ]
}
```

### 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `sample_id` | string | 是 | 样本标识，对应输入的 event_id。 |
| `fact_verifications` | FactVerification[] | 是 | 对 Step1 每条 key_relation 的逐条复核结果。数量与 Step1 的 key_relations 一一对应。 |
| `candidates` | Stage2Candidate[] | 是 | 违规候选列表，至少1条。若无违规则输出 `violation_category=["no_violation"]`。 |

### FactVerification 字段详解

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `relation_index` | int | 是 | 对应 Step1 key_relations 中的索引（从0开始）。 |
| `subject` | string | 是 | 从 Step1 继承的主体名称。 |
| `relation` | string | 是 | 从 Step1 继承的关系枚举。 |
| `object` | string | 是 | 从 Step1 继承的锚点枚举。 |
| `bbox` | int[4] | 是 | 从 Step1 继承的主体边界框。 |
| `visibility_level` | string | 是 | 主体在画面中的可见程度。取值：`clear`（完全可见）`partial`（部分可见）`tiny`（占比极小）`blurry`（模糊）`occluded`（严重遮挡） |
| `information_loss_type` | string | 是 | 信息缺失类型。取值：`none`（无缺失）`occlusion`（被遮挡）`boundary_truncation`（被图像边界裁剪） |
| `key_attributes_visible` | string[] | 是 | 实际可见的关键结构列表。例如电动车的 `["wheel", "body"]`，人的 `["head", "body"]`。若为空数组则表示关键结构不可见。 |
| `subject_visible` | bool | 是 | bbox 内是否可以看到该主体。 |
| `subject_match` | bool | 是 | bbox 内的主体类别是否与 Step1 声称的一致。 |
| `bbox_observation` | string | 是 | 对 bbox 区域的客观视觉描述。只描述看到了什么，不做违规判断。 |
| `global_context_observation` | string | 是 | 对全局上下文的客观观察。描述主体与周围环境的关系。 |
| `verification_result` | string | 是 | 事实复核结论。取值：`supported`（事实完全成立）`weakly_supported`（部分成立）`unsupported`（不成立）`unclear`（无法判断） |
| `verification_confidence` | float | 是 | 复核置信度，0.0-1.0。受 visibility_level 和 information_loss_type 约束。 |

#### verification_result 判定规则

| 条件 | 允许的 verification_result |
|---|---|
| visibility=clear, loss=none | supported（高置信允许） |
| visibility=clear, loss=occlusion 且关键结构可见 | supported（高置信允许） |
| visibility=partial | 最高 weakly_supported，confidence ≤ 0.8 |
| visibility=tiny 或 blurry | 禁止 supported，禁止高置信 positive |
| loss=boundary_truncation | 禁止 supported，必须降级 |
| 关键结构不可见 | 禁止 supported，必须降级 |

### Stage2Candidate 字段详解

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `violation_category` | string[] | 是 | 违规类别列表。取值来自违规类别枚举，或 `["no_violation"]` 表示无违规。 |
| `evidence_relation_indices` | int[] | 是 | 支撑该候选违规判断的 fact_verifications 索引列表。 |
| `evidence_reasoning` | string | 是 | 违规推理说明。只能引用 Step1 已出现的主体、锚点、关系和事实描述，不能自行推断。 |
| `relation_hint` | string | 否 | 关系提示，格式为 `"{subject} {relation} {object}"`，便于下游快速理解。 |
| `segmentation_targets` | string[] | 是 | 需要分割的目标主体列表，供下游 SAM3 使用。Step1-Step2 模式下通常为空。 |
| `confidence` | float | 是 | 违规置信度，0.0-1.0。受 verification_result 和 visibility_level 约束。 |
| `sample_category` | string | 是 | 样本类别。取值：`positive samples`（正样本，有违规）`negative samples`（负样本，无违规）`hard boundary samples`（边界样本） |

#### confidence 约束规则

| 条件 | confidence 上限 |
|---|---|
| verification_result=supported, visibility=clear, loss=none | 无限制（可到 1.0） |
| visibility=partial | ≤ 0.8 |
| verification_result=weakly_supported | ≤ 0.75 |
| visibility=tiny 或 blurry | 不允许高置信 |

---

## 五、完整输出结构

API 返回的完整 JSON 结构：

```json
{
  "event_id": "evt_35613fb47cc6adc2a129d691",
  "stage": "refined",
  "frame_seed": {
    "image_uri": "s3://test-image-bucket/1760525209346.jpg",
    "camera_id": "front",
    "location": "南山路",
    "device_id": "dog-17",
    "task_id": "patrol-http-001",
    "occur_time": "2026-03-09T10:00:00Z"
  },
  "stage1_output": { ... },
  "stage2_output": { ... },
  "event_version": 2
}
```

| 字段 | 说明 |
|---|---|
| `event_id` | 事件唯一标识，SHA-256 哈希生成 |
| `stage` | 固定为 `"refined"`，表示已完成两阶段分析 |
| `frame_seed` | 原始输入参数，原样保留 |
| `stage1_output` | Step1 VLM 原始输出，结构见第三节 |
| `stage2_output` | Step2 VLM 原始输出（经结果门禁过滤 candidates），结构见第四节 |
| `event_version` | 固定为 `2`，表示 Step1-Step2 流程版本 |

---

## 六、数据流概览

```
输入 EventSeed
  │
  ▼
Step1 VLM（系统提示词 + 用户提示词 + 图像）
  │
  ▼
Stage1Output（JSON Schema 校验）
  │
  ▼ Stage1Output JSON 原样传入 Step2
Step2 VLM（系统提示词 + 用户提示词 + Stage1Output JSON + 图像）
  │
  ▼
Stage2Output（JSON Schema 校验）
  │
  ▼
结果门禁（按 location + camera_id 过滤 candidates）
  │
  ▼
输出：stage1_output + stage2_output + 事件元数据
```

中间不做任何映射转换，Step1 和 Step2 的原始输出直接透传到最终结果。
