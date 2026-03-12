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

- “根据 `camera_id + location` 激活一组候选类别和位置规则”

### 7.2 推荐策略

引入一个新的概念：

- `SceneActivationPolicy`

它由两个维度构成：

1. `camera policy`
2. `location policy`

最终生成：

- `enabled_categories`
- `disabled_categories`
- `location_constraints`
- `scene_hint`

### 7.3 `camera_id` 维度建议

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

例如：

- `水坊街`
  - 店铺密集
  - 优先启用店铺类和占道类
  - 对 `staff_not_wear_mask` 可以保持启用

- `南山路`
  - 如果以道路通行场景为主
  - 可以提升道路占用、车辆违停、人宠类权重

### 7.5 合并策略

最终规则建议采用：

- `enabled_categories = camera_enabled ∩ location_enabled`
- `disabled_categories = camera_disabled ∪ location_disabled`
- `location_constraints = location_specific_rules`

这样可以避免某一侧单独放开导致类别过宽。

## 8. `VLM-1` prompt 设计调整

### 8.1 当前问题

当前 `VLM-1` prompt 更像通用全量识别提示。  
新 feature 引入后，prompt 必须有能力接收当前场景下：

- 哪些类别可以判断
- 哪些类别不应优先判断
- 当前片区有哪些位置约束

### 8.2 推荐方案

不要把全部规则硬塞回固定 `system prompt`，而是采用：

- 固定 `system prompt`
- 配置驱动的 `user prompt` 变量注入

新增可注入变量建议包括：

- `{camera_id}`
- `{location}`
- `{enabled_categories}`
- `{location_constraints}`
- `{scene_hint}`

### 8.3 预期效果

这样 `VLM-1` 在分析图像前，就知道：

- 当前图像来自哪一个朝向相机
- 当前在什么片区
- 当前应该优先判断哪些违规类别
- 当前片区有哪些额外限制

## 9. 配置文件设计

### 9.1 推荐新增配置块

建议在配置中新增：

- `scene_policies`

结构示意：

```yaml
scene_policies:
  cameras:
    front:
      enabled_categories:
        - motor_vehicle_illegal_parking
        - nonmotor_vehicle_illegal_parking
        - off_leash_dog_nuisance
      scene_hint: road-facing camera
    left:
      enabled_categories:
        - road_occupying_vendor
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
      scene_hint: storefront-facing camera

  locations:
    南山路:
      enabled_categories:
        - motor_vehicle_illegal_parking
        - nonmotor_vehicle_illegal_parking
        - goods_blocking_road
      location_constraints:
        - focus on roadside, sidewalk, bus-stop, and blind-path occupation

    水坊街:
      enabled_categories:
        - road_occupying_vendor
        - goods_blocking_road
        - unauthorized_electrical_wiring
        - staff_not_wear_mask
      location_constraints:
        - focus on storefront frontage, sidewalk occupation, and outdoor charging behavior
```

### 9.2 运行时结果

在 workflow 进入 `VLM-1` 前，先根据：

- `camera_id`
- `location`

组装出一份 `scene_activation_context`，供 prompt builder 使用。

## 10. 代码影响面

### 10.1 API 层

需要调整：

- `InspectionIngestRequest`
- 输入校验测试
- API ingress 测试

### 10.2 领域层

需要调整：

- `EventSeed`
- `ViolationEvent`
- `generate_event_id()`

### 10.3 prompt 层

需要调整：

- `ConfigurableInspectionPromptBuilder`
- `VLM-1 user prompt` 模板变量

### 10.4 workflow 层

需要增加：

- `scene activation context` 构造逻辑

建议不要把这个逻辑塞进 client 内部，而是在 workflow / bootstrap 附近完成，保持职责清晰。

### 10.5 配置层

需要新增：

- `scene_policies` 配置模型

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
4. 再调整 `VLM-1 prompt`
5. 最后更新 fixtures / tests / README

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

### 12.3 `VLM-1` prompt 测试

新增覆盖：

- `camera_id=left` 注入店铺类激活集合
- `camera_id=front` 注入道路类激活集合
- `location=水坊街` 注入片区约束

### 12.4 workflow 测试

新增覆盖：

- `scene_activation_context` 能正确传入 VLM-1
- 左右相机不再默认启用全量道路类

## 13. 推荐实施顺序

建议按以下顺序落地：

1. 输入 schema 变更
2. `EventSeed` / `event_id` 变更
3. 配置模型新增 `scene_policies`
4. workflow 组装 `scene_activation_context`
5. `VLM-1` prompt 模板注入
6. 测试与 fixtures 更新
7. README / 文档更新

## 14. 结论

这次 feature 的本质不是“字段替换”，而是：

- 从通用图像识别输入
- 升级到“带相机朝向与片区语义的巡检场景输入”

如果按本方案实现，系统将获得三个直接收益：

1. 输入契约更贴近机器狗真实采集模式
2. `VLM-1` 判断范围更受控，误判更少
3. 后续可以继续扩展为基于 `camera_id + location` 的精细化巡检策略系统
