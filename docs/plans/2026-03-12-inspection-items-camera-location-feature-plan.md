# `v1/inspection-items` 参数调整与场景激活策略方案

## 1. 文档目的

本文档用于规划当前 MVP 版本上一个新的输入契约升级：

- 去掉 `frame_id`
- 增加 `camera_id`
- 增加 `location`

并基于这两个新增字段，为 `VLM-1` 引入“按相机朝向与片区激活类别判断和位置约束”的能力。

本文档只定义 feature 方案，不直接描述实现代码。

## 2. 背景

当前 `v1/inspection-items` 接口使用的是较通用的输入结构：

- `image_uri`
- `frame_id`
- `device_id`
- `task_id`
- `occur_time`

但在真实业务中，机器狗搭载多个固定朝向相机：

- `front`
- `left`
- `right`

其中：

- `left` / `right` 更偏店铺侧场景
- `front` 更偏道路正前方、通行空间、车辆、人宠等场景

同时，`location` 传入的是片区名称，例如：

- `南山路`
- `水坊街`

这意味着 `VLM-1` 不应再总是对全部类别做统一判断，而应根据：

- `camera_id`
- `location`

动态激活合适的违规类别和位置约束。

## 3. 目标

这个 feature 的目标不是简单改字段名，而是完成以下升级：

1. 让输入契约更贴近真实采集方式
2. 让 `VLM-1` 从“全量泛判”转为“场景感知判别”
3. 降低无关类别误判
4. 为后续 location/camera 规则配置化打基础

## 4. 新输入契约

### 4.1 新版 `v1/inspection-items` 请求参数

建议将请求体调整为：

- `image_uri`
- `camera_id`
- `location`
- `device_id`
- `task_id`
- `occur_time`

移除：

- `frame_id`

### 4.2 字段定义

#### `camera_id`

表示这张图像来自哪一个固定朝向相机。当前建议至少支持：

- `front`
- `left`
- `right`

后续如果同一台机器狗存在更多相机标识，也允许扩展为：

- `front_wide`
- `left_close`
- `right_rear`

#### `location`

表示片区名称，而不是经纬度。例如：

- `南山路`
- `水坊街`

它的作用不是做几何定位，而是决定：

- 该片区允许关注哪些类目
- 该片区是否有特殊约束
- 该片区是否需要对某些类目降权或禁用

## 5. 领域模型调整

### 5.1 `EventSeed`

当前 `EventSeed` 需要改为：

- `image_uri`
- `camera_id`
- `location`
- `device_id`
- `task_id`
- `occur_time`

移除：

- `frame_id`

### 5.2 `ViolationEvent` / feedback

当前一些对外结果和失败结果中仍带有 `frame_id`。  
建议同步收敛为：

- 使用 `event_id` 作为主索引
- 把 `camera_id` / `location` 作为新的场景上下文字段

这样更符合当前真实输入来源。

## 6. `event_id` 生成策略调整

### 6.1 当前问题

当前 `event_id` 使用：

- `frame_id`
- `device_id`
- `task_id`
- `occur_time`

来生成。

一旦去掉 `frame_id`，必须重新定义稳定主键策略。

### 6.2 推荐方案

建议新的 `event_id` 原始拼接字段改为：

- `image_uri`
- `camera_id`
- `location`
- `device_id`
- `task_id`
- `occur_time`

推荐原因：

- `image_uri` 能补上原来 `frame_id` 的去重作用
- `camera_id` 能区分同一时刻不同朝向相机采集的图像
- `location` 能保证不同片区不会错误聚合

### 6.3 预期效果

调整后，去掉 `frame_id` 后仍然可以稳定生成 `event_id`，  
并且同一时刻来自不同朝向相机的图像不会误共享 `event_id`。  
同时 preliminary/refined 仍然可以共享稳定主键。

## 7. `VLM-1` 场景激活策略

### 7.1 设计目标

让 `VLM-1` 的判断从：

- “对全部标准类别统一判断”

变成：

- “根据 `camera_id + location` 联合决定最终分析类别集合与位置规则”

### 7.2 推荐策略

引入一个新的概念：

- `SceneActivationPolicy`

但这里不应简单理解为“相机策略”和“片区策略”各自独立，再做机械合并。  
根据当前业务语义，更准确的做法是：

1. `camera default policy`
2. `location default policy`
3. `camera + location override policy`

最终生成的是当前输入场景下的一份**最终激活策略**，包含：

- `enabled_categories`
- `disabled_categories`
- `priority_categories`
- `location_constraints`
- `scene_hint`

### 7.3 `camera_id` 维度建议

`camera_id` 的作用是提供朝向语义上的默认倾向，而不是单独决定最终类别集合。

#### `front`

建议优先激活：

- `motor_vehicle_illegal_parking`
- `nonmotor_vehicle_illegal_parking`
- `off_leash_dog_nuisance`
- `vagrants_blocking_roadway`
- `begging_blocking_roadway`
- `goods_blocking_road`

可降权或默认关闭：

- `staff_not_wear_mask`

原因：

- 前向相机更容易拍到道路、盲道、公交站台、路面通行空间
- 不适合做强依赖店铺内部或店员面部细节的判断

#### `left` / `right`

建议优先激活：

- `road_occupying_vendor`
- `goods_blocking_road`
- `unauthorized_electrical_wiring`
- `staff_not_wear_mask`

可降权：

- `motor_vehicle_illegal_parking`
- `nonmotor_vehicle_illegal_parking`

原因：

- 左右相机更偏店铺立面、门头、外摆、门前人行道
- 更适合店铺相关违规类目

### 7.4 `location` 维度建议

`location` 不直接决定相机朝向，但决定片区场景规则。  
它提供的是片区层面的默认约束，而不是最终类别集合。

例如：

- `水坊街`
  - 店铺密集
  - 优先启用店铺类和占道类
  - 对 `staff_not_wear_mask` 可以保持启用

- `南山路`
  - 如果以道路通行场景为主
  - 可以提升道路占用、车辆违停、人宠类权重

### 7.5 合并策略

第 7 节原先如果采用简单交集策略：

- `enabled_categories = camera_enabled ∩ location_enabled`

会无法表达真实业务需求。  
原因是当前场景不是“相机”和“片区”分别提供一组独立约束，最后简单求交，而是：

- `camera_id`
- `location`

共同决定当前应该检测哪些类别。

因此建议把最终规则改为以下优先级：

1. 优先查找 `camera + location` 的组合覆盖规则
2. 若不存在覆盖规则，再回退到：
   - `camera default policy`
   - `location default policy`
3. 若仍未命中，则使用全局默认规则

也就是说，真正的主决策层应当是：

- `SceneActivationPolicy(location, camera_id)`

而不是：

- `camera policy ∩ location policy`

### 7.6 组合规则示例

根据当前业务示例，可直接表达为：

- `front + 南山路`
  - 检测：除 `staff_not_wear_mask` 外的其他主要类别

- `left + 南山路`
  - 只检测：
    - `staff_not_wear_mask`
    - `goods_blocking_road`
    - `unauthorized_electrical_wiring`

- `right + 南山路`
  - 同 `left + 南山路`

这个例子说明，真实策略应允许某个组合直接定义：

- 最终启用集合
- 最终禁用集合
- 该组合下的优先类别
- 该组合下的位置约束

### 7.7 推荐配置结构

建议将配置结构改成三层：

```yaml
scene_policies:
  camera_defaults:
    front:
      enabled_categories:
        - motor_vehicle_illegal_parking
        - nonmotor_vehicle_illegal_parking
        - off_leash_dog_nuisance
      priority_categories:
        - motor_vehicle_illegal_parking
        - nonmotor_vehicle_illegal_parking
      scene_hint: road-facing camera

    left:
      enabled_categories:
        - road_occupying_vendor
        - goods_blocking_road
        - unauthorized_electrical_wiring
        - staff_not_wear_mask
      priority_categories:
        - goods_blocking_road
        - unauthorized_electrical_wiring
        - staff_not_wear_mask
      scene_hint: storefront-facing camera

    right:
      enabled_categories:
        - road_occupying_vendor
        - goods_blocking_road
        - unauthorized_electrical_wiring
        - staff_not_wear_mask
      priority_categories:
        - goods_blocking_road
        - unauthorized_electrical_wiring
        - staff_not_wear_mask
      scene_hint: storefront-facing camera

  location_defaults:
    南山路:
      enabled_categories:
        - road_occupying_vendor
        - goods_blocking_road
        - unauthorized_electrical_wiring
        - motor_vehicle_illegal_parking
        - nonmotor_vehicle_illegal_parking
        - vagrants_blocking_roadway
        - begging_blocking_roadway
        - off_leash_dog_nuisance
      location_constraints:
        - focus on roadside, sidewalk, storefront frontage, and pedestrian passage

    水坊街:
      enabled_categories:
        - road_occupying_vendor
        - goods_blocking_road
        - unauthorized_electrical_wiring
        - staff_not_wear_mask
      location_constraints:
        - focus on storefront frontage, sidewalk occupation, and outdoor charging behavior

  overrides:
    南山路:
      front:
        enabled_categories:
          - road_occupying_vendor
          - goods_blocking_road
          - unauthorized_electrical_wiring
          - motor_vehicle_illegal_parking
          - nonmotor_vehicle_illegal_parking
          - vagrants_blocking_roadway
          - begging_blocking_roadway
          - off_leash_dog_nuisance
        disabled_categories:
          - staff_not_wear_mask
        priority_categories:
          - motor_vehicle_illegal_parking
          - nonmotor_vehicle_illegal_parking
          - goods_blocking_road

      left:
        enabled_categories:
          - staff_not_wear_mask
          - goods_blocking_road
          - unauthorized_electrical_wiring
        priority_categories:
          - staff_not_wear_mask
          - goods_blocking_road
          - unauthorized_electrical_wiring

      right:
        enabled_categories:
          - staff_not_wear_mask
          - goods_blocking_road
          - unauthorized_electrical_wiring
        priority_categories:
          - staff_not_wear_mask
          - goods_blocking_road
          - unauthorized_electrical_wiring
```

### 7.8 运行时决策逻辑

运行时应按以下顺序生成 `scene_activation_context`：

1. 读取 `camera_defaults[camera_id]`
2. 读取 `location_defaults[location]`
3. 检查是否存在 `overrides[location][camera_id]`
4. 如果存在 override，直接以 override 为最终规则
5. 如果不存在 override，再按默认规则生成最终激活集合

最终交给 `VLM-1` 的上下文建议包括：

- `camera_id`
- `location`
- `enabled_categories`
- `disabled_categories`
- `priority_categories`
- `location_constraints`
- `scene_hint`

## 8. `VLM-1` prompt 设计调整

### 8.1 当前问题

当前 `VLM-1` prompt 更像一份通用全量识别提示。  
如果仍然沿用这种单体静态 `system prompt`，那么第 7 节得到的策略结果只能被塞进较轻的 `user prompt` 中，这会导致：

- 场景规则不处于高优先级控制位
- 不同相机朝向/片区组合的约束表达不够强
- 后续规则变更时只能继续堆叠长文本，而不是做结构化注入

因此，`VLM-1` 的提示词机制需要升级为：

- **结构化可注入的 `system prompt`**

### 8.2 设计目标

新的提示词方案应满足：

1. 全局巡检定义仍由 `system prompt` 主导
2. `camera_id + location` 对应的场景策略应在后端先解析，再将抽象语义注入到 `system prompt`
3. `user prompt` 仅承担“触发本次图像分析”的作用
4. 不同场景组合应能生成不同的最终 `system prompt`

### 8.3 推荐结构

建议将当前 `VLM-1 system prompt` 拆成 5 个结构段：

1. `role_block`
- 定义模型角色、巡检任务、基本职责

2. `scene_activation_block`
- 注入由第 7 节策略解析得到的当前场景策略

3. `category_focus_block`
- 注入当前 `priority_categories` 对应的精简类别定义摘要

4. `reasoning_block`
- 要求模型先分析环境，再做类别判断

5. `output_contract_block`
- 规定 JSON 输出字段、顺序和约束

最终运行时拼装逻辑应是：

```text
{role_block}

{scene_activation_block}

{category_focus_block}

{reasoning_block}

{output_contract_block}
```

### 8.4 `scene_activation_block` 注入内容

第 7 节解析出来的 `SceneActivationPolicy(location, camera_id)` 不应直接把原始控制字段或完整策略对象暴露给模型。  
它应先在后端被转换成更适合模型理解的抽象语义，再注入 `system prompt`。

当前建议仅注入以下字段：

- `{scene_hint}`
- `{priority_categories}`
- `{open_risk_guidance}`

其中：

- `scene_hint`
  - 描述当前画面的场景抽象语义，例如“道路正前方通行空间场景”或“店铺立面与门前人行道场景”
- `priority_categories`
  - 描述当前场景下应优先关注的标准类别
- `open_risk_guidance`
  - 描述开放通用风险的输出原则

推荐注入后的文本结构例如：

```text
Current scene focus:
- scene_hint: storefront-facing side camera in roadside commercial block
- priority_categories:
  - staff_not_wear_mask
  - goods_blocking_road
  - unauthorized_electrical_wiring
- open_risk_guidance:
  - if visible evidence strongly suggests a risk outside the priority standard categories, output open_risk with a concise risk type
```

### 8.5 模型使用规则

这一块不再要求模型理解 `camera_id`、`location`、`enabled_categories`、`disabled_categories` 这些后端控制字段。  
模型只需要理解：

- 当前场景是什么
- 当前应优先关注哪些类别
- 当前如何处理标准类目之外的风险

推荐增加以下规则语义：

- `priority_categories` 内的类别应优先审查
- 若图像中未出现 `priority_categories` 内的充分证据，可继续做全局环境分析，但不要偏离当前场景重点
- 若出现明显但不属于当前优先标准类目的异常现象，可按 `open_risk_guidance` 输出 `open_risk`

### 8.6 `user prompt` 的角色

在这个方案下，`user prompt` 不再承担主要策略控制职责，而应保持轻量。

建议 `user prompt` 仅保留类似：

```text
Analyze this inspection image under the configured scene policy and output the required JSON.
```

这意味着：

- 全局定义和场景约束都进 `system prompt`
- `user prompt` 只触发本次任务
- 图像仍然通过 `image_url` 多模态输入传递

### 8.7 运行时生成流程

建议运行时按以下顺序生成最终用于处理该图片的提示词：

1. API 接收：
- `image_uri`
- `camera_id`
- `location`
- `device_id`
- `task_id`
- `occur_time`

2. workflow 或其前置解析层计算：
- `SceneActivationPolicy(location, camera_id)`

3. 后端将策略结果转换为模型可见的抽象语义：
- `scene_hint`
- `priority_categories`
- `open_risk_guidance`

4. 将这些字段格式化为：
- `scene_activation_block`

5. 使用配置模板组装最终 `system prompt`

6. 使用轻量固定模板生成 `user prompt`

7. 与 `image_url` 一起组成最终 `messages`

最终结果不是“一份静态 prompt”，而是：

- 动态 `system prompt`
- 轻量 `user prompt`
- 当前图片 `image_url`

三者组成的最终模型输入。

### 8.8 配置结构要求

为了支持这种模式，当前配置文件中的 `prompts.preliminary.system` 不应再只是一整段最终成稿，而应拆成可组合块。

推荐改成：

- `prompts.preliminary.role_block`
- `prompts.preliminary.scene_activation_block_template`
- `prompts.preliminary.category_focus_block_template`
- `prompts.preliminary.reasoning_block`
- `prompts.preliminary.output_contract_block`
- `prompts.preliminary.user`
- `category_registry`
- `open_risk_registry`

其中：

- `prompts.preliminary.*` 负责 prompt 骨架
- `category_registry` 负责标准类别定义与关系焦点
- `open_risk_registry` 负责开放风险 guidance
- 前 5 块在运行时拼成最终 `system prompt`
- `user` 保持轻量短模板

### 8.9 预期效果

采用这种结构后，`VLM-1` 在处理图片前就能通过 `system prompt` 明确知道：

- 当前场景的抽象语义是什么
- 当前要优先检查哪些类别
- 当前如何处理标准类目之外的开放通用风险

这样第 7 节策略就不再只是后端内部规则，而会真正成为模型推理条件的一部分。

## 9. 配置文件设计

### 9.1 推荐新增配置块

建议把配置设计拆成两部分：

1. `scene_policies`
2. `prompts.preliminary.*_block`

也就是：

- 第 7 节负责描述“当前场景下最终允许判断什么”
- 第 8 节负责描述“这些策略如何被注入 VLM-1 system prompt”

### 9.2 `scene_policies` 配置结构

`scene_policies` 应负责提供：

- `camera_defaults`
- `location_defaults`
- `overrides`

结构示意：

```yaml
scene_policies:
  camera_defaults:
    front:
      enabled_categories:
        - motor_vehicle_illegal_parking
        - nonmotor_vehicle_illegal_parking
        - off_leash_dog_nuisance
      priority_categories:
        - motor_vehicle_illegal_parking
        - nonmotor_vehicle_illegal_parking
      scene_hint: road-facing camera

    left:
      enabled_categories:
        - road_occupying_vendor
        - goods_blocking_road
        - unauthorized_electrical_wiring
        - staff_not_wear_mask
      priority_categories:
        - goods_blocking_road
        - unauthorized_electrical_wiring
        - staff_not_wear_mask
      scene_hint: storefront-facing camera

    right:
      enabled_categories:
        - road_occupying_vendor
        - goods_blocking_road
        - unauthorized_electrical_wiring
        - staff_not_wear_mask
      priority_categories:
        - goods_blocking_road
        - unauthorized_electrical_wiring
        - staff_not_wear_mask
      scene_hint: storefront-facing camera

  location_defaults:
    南山路:
      enabled_categories:
        - road_occupying_vendor
        - goods_blocking_road
        - unauthorized_electrical_wiring
        - motor_vehicle_illegal_parking
        - nonmotor_vehicle_illegal_parking
        - vagrants_blocking_roadway
        - begging_blocking_roadway
        - off_leash_dog_nuisance
      location_constraints:
        - focus on roadside, sidewalk, storefront frontage, and pedestrian passage

    水坊街:
      enabled_categories:
        - road_occupying_vendor
        - goods_blocking_road
        - unauthorized_electrical_wiring
        - staff_not_wear_mask
      location_constraints:
        - focus on storefront frontage, sidewalk occupation, and outdoor charging behavior

  overrides:
    南山路:
      front:
        enabled_categories:
          - road_occupying_vendor
          - goods_blocking_road
          - unauthorized_electrical_wiring
          - motor_vehicle_illegal_parking
          - nonmotor_vehicle_illegal_parking
          - vagrants_blocking_roadway
          - begging_blocking_roadway
          - off_leash_dog_nuisance
        disabled_categories:
          - staff_not_wear_mask
        priority_categories:
          - motor_vehicle_illegal_parking
          - nonmotor_vehicle_illegal_parking
          - goods_blocking_road

      left:
        enabled_categories:
          - staff_not_wear_mask
          - goods_blocking_road
          - unauthorized_electrical_wiring
        priority_categories:
          - staff_not_wear_mask
          - goods_blocking_road
          - unauthorized_electrical_wiring

      right:
        enabled_categories:
          - staff_not_wear_mask
          - goods_blocking_road
          - unauthorized_electrical_wiring
        priority_categories:
          - staff_not_wear_mask
          - goods_blocking_road
          - unauthorized_electrical_wiring
```

### 9.3 `prompts.preliminary` 配置结构

为支持第 8 节的结构化 `system prompt`，当前 `prompts.preliminary.system` 不应继续保持单段文本，而应拆成以下块：

- `role_block`
- `scene_activation_block_template`
- `category_focus_block_template`
- `reasoning_block`
- `output_contract_block`
- `user`

同时，全量类别定义不应继续直接写进最终 prompt，而应拆到独立配置：

- `category_registry`
- `open_risk_registry`

结构示意：

```yaml
prompts:
  preliminary:
    role_block: |
      You are a city-street visual inspection model for a robot-dog patrol backend.

    scene_activation_block_template: |
      Current scene activation policy:
      - scene_hint: {scene_hint}
      - priority_categories: {priority_categories}
      - open_risk_guidance: {open_risk_guidance}

    category_focus_block_template: |
      Prioritized category references:
      {category_definitions}

    reasoning_block: |
      Always analyze the full environment before deciding the violation category.

    output_contract_block: |
      You must output JSON only, in this exact order:
      ...

    user: |
      Analyze this inspection image under the configured scene policy and output the required JSON.

category_registry:
  goods_blocking_road:
    definition: 货物、材料、宣传牌、垃圾等堆放在人行道并阻碍通行
    common_objects: [goods, materials, signboard, trash, storefront_entrance, sidewalk]
    relation_focus: [objects_on_sidewalk, obstruct_pedestrian_passage]
    exceptions: []

open_risk_registry:
  guidance: |
    If obvious risk evidence exists but does not fit the prioritized standard categories,
    output violation_category="open_risk" with a concise open_risk_type.
```

### 9.4 运行时配置结果

运行时应由后端完成两次组合：

1. `scene_policies` 解析成：
   - `scene_activation_context`
2. `scene_activation_context.priority_categories` 从 `category_registry` 中挑选少量类别定义并渲染成 `category_definitions`
3. `prompts.preliminary.*_block` + `scene_activation_context` + `category_definitions`
   - 组合成最终 `system prompt`

最终 `VLM-1` 使用的是：

- 动态 `system prompt`
- 轻量 `user prompt`
- `image_url`

## 10. 代码影响面

### 10.1 API 层

需要调整：

- `InspectionIngestRequest`
- 输入校验测试
- API ingress 测试

并且要同步收敛：

- API 示例请求
- API 失败响应中的上下文字段

### 10.2 领域层

需要调整：

- `EventSeed`
- `ViolationEvent`
- `generate_event_id()`

并建议新增：

- `SceneActivationContext`
- `SceneActivationPolicy`

### 10.3 prompt 层

需要调整：

- `ConfigurableInspectionPromptBuilder`
- `VLM-1 system prompt` 结构化拼装逻辑
- `scene_activation_block_template` 渲染逻辑

这里的重点不再是“往 user prompt 里塞变量”，而是：

- 先拼装 `system prompt`
- 再附加轻量 `user prompt`

### 10.4 workflow 层

需要增加：

- `scene activation context` 构造逻辑
- `camera_id + location` 到最终策略的解析调用

建议不要把这个逻辑塞进 client 内部，而是在 workflow / bootstrap 附近完成，保持职责清晰。  
推荐新增一层类似：

- `ScenePolicyResolver`
- `PreliminaryPromptComposer`

### 10.5 配置层

需要新增：

- `scene_policies` 配置模型
- 结构化 `preliminary prompt blocks` 配置模型

### 10.6 测试层

需要同步新增：

- `scene policy resolver` 专项测试
- `preliminary system prompt composer` 专项测试
- 不同 `camera_id + location` 组合下的 prompt 快照测试

## 11. 兼容与迁移策略

### 11.1 兼容策略

建议这次 feature 直接升级主契约，不做长期双字段兼容。

即：

- 新版接口不再接受 `frame_id`
- 客户端必须改为传：
  - `camera_id`
  - `location`

原因：

- 当前 still MVP 阶段，改接口成本可控
- 继续保留 `frame_id` 只会增加混乱

### 11.2 迁移步骤

建议顺序：

1. 先改 `EventSeed` 和 API schema
2. 再改 `event_id` 生成
3. 再补 `scene_policies` 配置与读取
4. 再拆分 `prompts.preliminary` 为结构化 blocks
5. 再实现 `SceneActivationPolicy` 解析
6. 再实现 `VLM-1 system prompt` 动态拼装
7. 最后更新 fixtures / tests / README

### 11.3 迁移结果要求

迁移完成后应保证：

- 新版请求体不再依赖 `frame_id`
- 当前场景组合的激活类别是可解释、可配置、可测试的
- `VLM-1` 最终使用的 `system prompt` 能体现当前场景的抽象语义与重点类别，而不是直接暴露控制字段

## 12. 测试计划

### 12.1 API 测试

新增覆盖：

- 新请求体成功
- 缺 `camera_id` 失败
- 缺 `location` 失败
- 继续传 `frame_id` 不再满足新版契约

### 12.2 `event_id` 测试

新增覆盖：

- 不同朝向相机输入生成不同 `event_id`
- 不同 `location` 生成不同 `event_id`
- 相同输入生成稳定 `event_id`

### 12.3 `SceneActivationPolicy` 测试

新增覆盖：

- `front + 南山路` 命中 override
- `left + 南山路` 命中店铺类 override
- `right + 南山路` 命中与左相机一致的 override
- 不存在 override 时正确回退到默认规则

### 12.4 `VLM-1 system prompt` 组装测试

新增覆盖：

- `scene_activation_block` 是否正确拼装
- `scene_hint / priority_categories / open_risk_guidance` 是否全部进 `system prompt`
- `camera_id / location / enabled_categories / disabled_categories / location_constraints` 是否不会直接进入 `system prompt`
- `front + 南山路` 与 `left + 南山路` 生成的最终 `system prompt` 明显不同

### 12.5 `VLM-1` 处理测试

新增覆盖：

- 不同 `camera_id + location` 组合下发送给 VLM-1 的 `messages` 是否符合预期
- `user prompt` 是否保持轻量且不承载场景控制字段
- 图像是否继续通过 `image_url` 传递

### 12.6 workflow 测试

新增覆盖：

- `scene_activation_context` 能正确传入 VLM-1
- 左右相机在 `南山路` 下不再默认启用全量道路类
- 前相机在 `南山路` 下仍可启用除 `staff_not_wear_mask` 外的大部分类别

## 13. 推荐实施顺序

建议按以下顺序落地：

1. 输入 schema 变更
2. `EventSeed` / `event_id` 变更
3. 配置模型新增 `scene_policies`
4. 配置模型新增 `prompts.preliminary.*_block`
5. 实现 `SceneActivationPolicy` 解析
6. workflow 组装 `scene_activation_context`
7. 实现 `VLM-1 system prompt` 动态拼装
8. 测试与 fixtures 更新
9. README / 文档更新

## 14. 结论

这次 feature 的本质不是“字段替换”，而是：

- 从通用图像识别输入
- 升级到“带相机朝向与片区语义的巡检场景输入”

如果按本方案实现，系统将获得三个直接收益：

1. 输入契约更贴近机器狗真实采集模式
2. `VLM-1` 判断范围更受控，误判更少
3. 后续可以继续扩展为基于 `camera_id + location` 的精细化巡检策略系统
